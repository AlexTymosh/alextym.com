from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import LiveResponse, ReadyResponse, WarmupResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    return HealthService(settings=settings)


@router.get("/health/live", response_model=LiveResponse)
async def live(service: HealthService = Depends(get_health_service)) -> LiveResponse:
    return service.live()


@router.get("/health/ready", response_model=ReadyResponse)
async def ready(service: HealthService = Depends(get_health_service)) -> ReadyResponse:
    return service.ready()


@router.get("/warmup", response_model=WarmupResponse)
async def warmup(service: HealthService = Depends(get_health_service)) -> WarmupResponse:
    return service.warmup()
