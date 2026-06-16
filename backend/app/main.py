from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.chat import router as chat_router
from app.api.contact import router as contact_router
from app.api.escalation import router as escalation_router
from app.api.health import router as health_router
from app.api.telegram import router as telegram_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.loki import shutdown_loki_exporter
from app.core.metrics import configure_metrics
from app.middleware.request_context import RequestContextMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        shutdown_loki_exporter(timeout_seconds=2.0)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        RequestContextMiddleware,
        request_id_header=settings.request_id_header,
    )
    _configure_cors(app, settings)
    app.include_router(health_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(contact_router, prefix="/api")
    app.include_router(escalation_router, prefix="/api")
    app.include_router(telegram_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    configure_metrics(app, settings)
    return app


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    allowed_origins = _get_allowed_cors_origins(settings)
    if not allowed_origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


def _get_allowed_cors_origins(settings: Settings) -> list[str]:
    origins = {settings.frontend_origin.rstrip("/")}

    if settings.environment.lower() in {"local", "development", "dev", "test"}:
        origins.update(
            {
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            }
        )

    return sorted(origin for origin in origins if origin)


app = create_app()
