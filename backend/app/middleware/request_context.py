from __future__ import annotations

import re
import uuid
from time import perf_counter
from typing import Any

import structlog
from starlette.datastructures import MutableHeaders
from structlog.contextvars import bind_contextvars, clear_contextvars

DEFAULT_REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")

logger = structlog.get_logger(__name__)


class RequestContextMiddleware:
    """Bind request context to all logs emitted during an HTTP request."""

    def __init__(
        self,
        app,
        *,
        request_id_header: str = DEFAULT_REQUEST_ID_HEADER,
    ) -> None:
        self.app = app
        self._request_id_header = request_id_header

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = perf_counter()
        request_id = _request_id_from_scope(scope, self._request_id_header)
        method = str(scope.get("method", "UNKNOWN"))
        status_code: int | None = None
        response_logged = False

        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            method=method,
            route=_route_label(scope),
        )

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal response_logged, status_code

            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers[self._request_id_header] = request_id
                bind_contextvars(route=_route_label(scope))

            if _is_final_response_body(message) and not response_logged:
                response_logged = True
                _log_completed_response(
                    start_time=start_time,
                    status_code=status_code,
                )

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            logger.exception(
                "http.request.failed",
                message="HTTP request failed.",
                duration_ms=_duration_ms(start_time),
                error_type=type(exc).__name__,
            )
            raise
        finally:
            clear_contextvars()


def _log_completed_response(
    *,
    start_time: float,
    status_code: int | None,
) -> None:
    resolved_status_code = status_code if status_code is not None else 500
    logger.info(
        "http.request.completed",
        message="HTTP request completed.",
        status_code=resolved_status_code,
        status_class=_status_class(resolved_status_code),
        duration_ms=_duration_ms(start_time),
    )


def _is_final_response_body(message: dict[str, Any]) -> bool:
    is_response_body = message["type"] == "http.response.body"
    is_final_body = message.get("more_body") is not True
    return is_response_body and is_final_body


def _request_id_from_scope(scope: dict[str, Any], header_name: str) -> str:
    raw_value = _header_value(scope.get("headers", []), header_name)
    if raw_value is not None:
        candidate = raw_value.strip()
        if _REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
    return f"req_{uuid.uuid4().hex}"


def _header_value(headers: list[tuple[bytes, bytes]], header_name: str) -> str | None:
    expected_name = header_name.casefold().encode("latin-1")
    for raw_name, raw_value in headers:
        if raw_name.lower() == expected_name:
            return raw_value.decode("latin-1")
    return None


def _duration_ms(start_time: float) -> int:
    return int((perf_counter() - start_time) * 1000)


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def _route_label(scope: dict[str, Any]) -> str:
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path

    path = scope.get("path")
    if isinstance(path, str) and path:
        return _normalise_unmatched_path(path)
    return "unknown"


def _normalise_unmatched_path(path: str) -> str:
    if re.fullmatch(r"/api/escalations/[^/]+/messages", path):
        return "/api/escalations/{handoff_id}/messages"
    if re.fullmatch(r"/api/escalations/[^/]+/close", path):
        return "/api/escalations/{handoff_id}/close"
    if re.fullmatch(r"/api/escalations/[^/]+/stream", path):
        return "/api/escalations/{handoff_id}/stream"
    return path
