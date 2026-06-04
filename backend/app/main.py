from fastapi import FastAPI

from app.api.analytics import router as analytics_router
from app.api.chat import router as chat_router
from app.api.contact import router as contact_router
from app.api.escalation import router as escalation_router
from app.api.health import router as health_router
from app.api.telegram import router as telegram_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import configure_metrics
from app.middleware.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.add_middleware(
        RequestContextMiddleware,
        request_id_header=settings.request_id_header,
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(contact_router, prefix="/api")
    app.include_router(escalation_router, prefix="/api")
    app.include_router(telegram_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    configure_metrics(app, settings)
    return app


app = create_app()
