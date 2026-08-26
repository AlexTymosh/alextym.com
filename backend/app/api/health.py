from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.rag.readiness import get_rag_readiness_probe
from app.schemas.health import LiveResponse, ReadyResponse, WarmupResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    return HealthService(
        settings=settings,
        rag_readiness_probe=get_rag_readiness_probe(settings),
    )


@router.get("/health/live", response_model=LiveResponse)
async def live(service: HealthService = Depends(get_health_service)) -> LiveResponse:
    return service.live()


@router.get("/health/ready", response_model=ReadyResponse)
def ready(
    response: Response,
    service: HealthService = Depends(get_health_service),
) -> ReadyResponse:
    readiness = service.ready()
    if readiness.status == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return readiness


@router.get("/warmup", response_model=WarmupResponse)
async def warmup(service: HealthService = Depends(get_health_service)) -> WarmupResponse:
    return service.warmup()
