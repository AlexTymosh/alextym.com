from __future__ import annotations

import secrets

import structlog
from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import Settings
from app.core.domain_metrics import domain_metrics_payload

logger = structlog.get_logger(__name__)


def configure_metrics(app: FastAPI, settings: Settings) -> None:
    """Configure protected Prometheus-compatible metrics for the backend."""

    if not settings.metrics_enabled:
        return

    if not settings.metrics_token:
        logger.warning(
            "metrics.disabled_missing_token",
            message="Metrics endpoint was not exposed because METRICS_TOKEN is empty.",
        )
        return

    registry = CollectorRegistry(auto_describe=True)
    app.state.metrics_registry = registry
    _instrument_app(app, settings, registry)
    app.add_api_route(
        settings.metrics_path,
        _metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )


def _instrument_app(
    app: FastAPI,
    settings: Settings,
    registry: CollectorRegistry,
) -> None:
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[settings.metrics_path],
        registry=registry,
    )
    instrumentator.instrument(app)


async def _metrics_endpoint(request: Request) -> Response:
    settings = request.app.state.settings
    _verify_metrics_token(request, settings)
    return Response(
        content=_metrics_payload(request),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


def _metrics_payload(request: Request) -> bytes:
    registry = getattr(request.app.state, "metrics_registry", None)
    if registry is None:
        return domain_metrics_payload()
    return generate_latest(registry) + domain_metrics_payload()


def _verify_metrics_token(request: Request, settings: Settings) -> None:
    if not settings.metrics_enabled or not settings.metrics_token:
        raise _not_found()

    expected_header = f"Bearer {settings.metrics_token}"
    received_header = request.headers.get("authorization", "")
    if secrets.compare_digest(received_header, expected_header):
        return

    logger.warning(
        "metrics.auth.failed",
        message="Metrics endpoint authentication failed.",
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Metrics endpoint authentication failed.",
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
