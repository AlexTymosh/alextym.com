from __future__ import annotations

import secrets

import structlog
from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import Settings

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

    _instrument_app(app, settings)
    app.add_api_route(
        settings.metrics_path,
        _metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )


def _instrument_app(app: FastAPI, settings: Settings) -> None:
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[settings.metrics_path],
    )
    instrumentator.instrument(app)


async def _metrics_endpoint(request: Request) -> Response:
    settings = request.app.state.settings
    _verify_metrics_token(request, settings)
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


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
