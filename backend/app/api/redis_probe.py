from secrets import compare_digest
from time import perf_counter

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.schemas.redis_probe import RedisProbeResponse
from app.services.redis_probe import RedisProbeError, RedisProbeService


router = APIRouter()
logger = structlog.get_logger(__name__)


def get_redis_probe_service(request: Request) -> RedisProbeService:
    settings = request.app.state.settings
    if not settings.redis_probe_token:
        raise HTTPException(status_code=404, detail="Not found")
    received = request.headers.get("Authorization", "").encode("utf-8")
    expected = f"Bearer {settings.redis_probe_token}".encode("utf-8")
    if not compare_digest(received, expected):
        raise HTTPException(status_code=403, detail="Forbidden")
    return RedisProbeService(settings.upstash_redis_rest_url, settings.upstash_redis_rest_token)


@router.post(
    "/internal/probes/redis",
    response_model=RedisProbeResponse,
    include_in_schema=False,
)
async def probe_redis(
    response: Response,
    service: RedisProbeService = Depends(get_redis_probe_service),
) -> RedisProbeResponse:
    started = perf_counter()
    try:
        await service.check()
    except RedisProbeError as exc:
        logger.warning(
            "redis_probe_failed",
            error_code=exc.code,
            duration_seconds=round(perf_counter() - started, 3),
        )
        raise HTTPException(
            status_code=503,
            detail="Redis check failed",
            headers={"Cache-Control": "no-store"},
        ) from None

    logger.info("redis_probe_succeeded", duration_seconds=round(perf_counter() - started, 3))
    response.headers["Cache-Control"] = "no-store"
    return RedisProbeResponse()
