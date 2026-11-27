import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fleet_hub.bootstrap import prepare_demo_database
from fleet_hub.router import configure_host_access, router as fleet_router
from workforce_intelligence.router import router as workforce_router
from preferans.router import make_realtime_router, router as preferans_router
from sameplace.router import router as sameplace_router
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.chat import router as chat_router
from app.api.contact import router as contact_router
from app.api.escalation import router as escalation_router
from app.api.health import router as health_router
from app.api.lab_identity import router as lab_identity_router
from app.api.redis_probe import router as redis_probe_router
from app.api.telegram import router as telegram_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.loki import shutdown_loki_exporter
from app.core.metrics import configure_metrics
from app.llm.workforce_voice import WorkforceVoiceOpenAI
from app.middleware.request_context import RequestContextMiddleware
from app.security.workforce_demo import require_workforce_member, router as workforce_access_router
from app.security.fleet_access import guard_fleet_routes, require_fleet_access
from app.security.preferans_access import require_preferans_member, verify_preferans_realtime
from app.security.sameplace_access import require_sameplace_member


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Prepare optional Fleet storage before serving requests. Failures must not
    # take down the main portfolio/chat site; Fleet retains lazy retry on use.
    _app.state.fleet_bootstrap_status = "disabled"
    try:
        if await run_in_threadpool(prepare_demo_database):
            _app.state.fleet_bootstrap_status = "ready"
    except Exception:
        _app.state.fleet_bootstrap_status = "failed"
        logger.exception("Optional Fleet SQLite initialization failed at startup")
    try:
        yield
    finally:
        shutdown_loki_exporter(timeout_seconds=2.0)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    if settings.openai_api_key.strip() and settings.openai_model.strip():
        app.state.workforce_voice_provider = WorkforceVoiceOpenAI(settings)
    app.add_middleware(
        RequestContextMiddleware,
        request_id_header=settings.request_id_header,
    )
    _configure_cors(app, settings)
    app.include_router(health_router, prefix="/api")
    app.include_router(lab_identity_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(contact_router, prefix="/api")
    app.include_router(escalation_router, prefix="/api")
    app.include_router(telegram_router, prefix="/api")
    configure_host_access(app, require_fleet_access)
    app.include_router(fleet_router, prefix="/api", dependencies=[Depends(guard_fleet_routes)])
    app.include_router(workforce_access_router, prefix="/api")
    # All Workforce data routes require a valid backend-signed demo session.
    app.include_router(
        workforce_router, prefix="/api", dependencies=[Depends(require_workforce_member)]
    )
    app.include_router(
        preferans_router, prefix="/api", dependencies=[Depends(require_preferans_member)]
    )
    # The WebSocket does not use the HTTP Request dependency; the dedicated
    # adapter redeems an authenticated ticket and rechecks the same host guard.
    app.include_router(make_realtime_router(verify_preferans_realtime), prefix="/api")
    app.include_router(
        sameplace_router, prefix="/api", dependencies=[Depends(require_sameplace_member)]
    )
    app.include_router(analytics_router, prefix="/api")
    app.include_router(redis_probe_router)
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
