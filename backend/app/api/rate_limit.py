from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.services.rate_limit import (
    RateLimitExceeded,
    client_identifier_from_request,
    get_rate_limiter,
)


def enforce_chat_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _enforce_daily_rate_limit(
        request=request,
        scope="chat",
        limit=settings.chat_daily_limit_per_ip,
        enabled=settings.rate_limiting_enabled,
    )


def enforce_contact_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _enforce_daily_rate_limit(
        request=request,
        scope="contact",
        limit=settings.contact_daily_limit_per_ip,
        enabled=settings.rate_limiting_enabled,
    )


def enforce_escalation_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _enforce_daily_rate_limit(
        request=request,
        scope="escalation",
        limit=settings.escalation_daily_limit_per_ip,
        enabled=settings.rate_limiting_enabled,
    )


def enforce_escalation_message_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _enforce_daily_rate_limit(
        request=request,
        scope="escalation_message",
        limit=settings.escalation_message_daily_limit_per_ip,
        enabled=settings.rate_limiting_enabled,
    )


def _enforce_daily_rate_limit(
    *,
    request: Request,
    scope: str,
    limit: int,
    enabled: bool,
) -> None:
    if not enabled:
        return

    identifier = client_identifier_from_request(request)
    try:
        get_rate_limiter().check(scope=scope, identifier=identifier, limit=limit)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily request limit reached. Please try again later.",
        ) from exc
