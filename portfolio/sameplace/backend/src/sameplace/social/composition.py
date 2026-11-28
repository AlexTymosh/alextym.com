"""Project-owned composition; the website continues mounting one public factory."""

import os
from urllib.parse import urlsplit
from fastapi import APIRouter
from ..rooms.api import make_room_router as make_core_router
from ..rooms.quota import QuotaCircuit
from ..rooms.rate_limit import RequestLimiter
from ..decor.api import make_decor_router
from .api import make_social_router
from .hub import Hub


def configured_realtime():
    return (
        os.getenv("SAMEPLACE_REALTIME_ENABLED") == "true"
        and os.getenv("SAMEPLACE_REALTIME_SINGLE_WORKER") == "true"
        and os.getenv("WEB_CONCURRENCY") == "1"
    )


def configured_origin(origin):
    configured = {
        item.strip()
        for item in os.getenv("SAMEPLACE_REALTIME_ORIGINS", "").split(",")
        if item.strip()
    }
    if origin not in configured:
        return False
    try:
        parsed = urlsplit(origin)
        return bool(
            parsed.netloc
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
            and (
                parsed.scheme == "https"
                or (
                    not os.getenv("RENDER")
                    and parsed.scheme == "http"
                    and parsed.hostname in {"127.0.0.1", "localhost"}
                )
            )
        )
    except ValueError:
        return False


def make_room_router(
    identify,
    database_provider,
    enabled=lambda: True,
    realtime_enabled=configured_realtime,
    allowed_origin=configured_origin,
):
    hub = Hub()
    circuit = QuotaCircuit()
    limiter = RequestLimiter()

    def changed(action, result, command):
        slug = result.get("slug")
        if action == "archive" and slug:
            hub.invalidate(slug)
        elif action in {"block", "remove"} and slug:
            hub.invalidate(slug, command.uid)
        else:
            hub.fence(slug)

    router = APIRouter()
    router.include_router(
        make_core_router(
            identify,
            database_provider,
            enabled,
            on_change=changed,
            circuit=circuit,
            limiter=limiter,
        )
    )
    router.include_router(
        make_social_router(
            identify,
            database_provider,
            enabled,
            realtime_enabled,
            allowed_origin,
            hub,
            circuit,
            limiter,
        )
    )
    router.include_router(
        make_decor_router(identify, database_provider, enabled, hub, circuit, limiter)
    )
    return router
