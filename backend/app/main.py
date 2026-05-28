from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.contact import router as contact_router
from app.api.escalation import router as escalation_router
from app.api.health import router as health_router
from app.api.telegram import router as telegram_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(contact_router, prefix="/api")
    app.include_router(escalation_router, prefix="/api")
    app.include_router(telegram_router, prefix="/api")
    return app


app = create_app()
