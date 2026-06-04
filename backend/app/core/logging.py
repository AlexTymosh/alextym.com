from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from app.core.config import Settings

SENSITIVE_LOG_KEYS = {
    "api_key",
    "authorization",
    "contact_email",
    "contact_from_email",
    "contact_target_email",
    "email",
    "handoff_id",
    "ip",
    "llm_output",
    "message_text",
    "openai_api_key",
    "password",
    "prompt",
    "qdrant_api_key",
    "raw_ip",
    "resend_api_key",
    "secret",
    "telegram_bot_token",
    "telegram_owner_chat_id",
    "token",
    "transcript",
    "user_message",
}

REDACTED_VALUE = "[redacted]"
NOISY_ACCESS_LOGGERS = ("httpx", "uvicorn.access")


def configure_logging(settings: Settings) -> None:
    """Configure privacy-safe structured logging for the backend service."""

    structlog.reset_defaults()
    log_level = _coerce_log_level(settings.log_level)
    renderer = _build_renderer(settings.log_format)
    shared_processors = _shared_processors(settings)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    for logger_name in NOISY_ACCESS_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def _shared_processors(settings: Settings) -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        _add_service_context(settings),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        _uppercase_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(
            fmt="iso",
            key="timestamp",
            utc=True,
        ),
        _redact_sensitive_log_fields,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]


def _build_renderer(log_format: str) -> Any:
    if log_format == "console":
        return structlog.dev.ConsoleRenderer()
    return structlog.processors.JSONRenderer()


def _add_service_context(settings: Settings):
    def processor(
        _logger: Any,
        _method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        event_dict.setdefault("service", settings.service_name)
        event_dict.setdefault("service_version", settings.service_version)
        event_dict.setdefault("environment", settings.environment)
        return event_dict

    return processor


def _uppercase_log_level(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    level = event_dict.get("level")
    if isinstance(level, str):
        event_dict["level"] = level.upper()
    return event_dict


def _redact_sensitive_log_fields(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if _is_sensitive_key(key):
            event_dict[key] = REDACTED_VALUE
    return event_dict


def _is_sensitive_key(key: str) -> bool:
    normalized_key = key.casefold()
    if normalized_key in SENSITIVE_LOG_KEYS:
        return True
    return any(
        sensitive_fragment in normalized_key
        for sensitive_fragment in ("password", "secret", "token", "api_key")
    )


def _coerce_log_level(value: str) -> int:
    return getattr(logging, value.strip().upper(), logging.INFO)
