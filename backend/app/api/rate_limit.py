from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.services.rate_limit import (
    RateLimitExceeded,
    RateLimitStoreError,
    build_rate_limiter,
    client_identifier_from_request,
    get_rate_limiter,
)


def enforce_chat_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _enforce_daily_rate_limit(
        request=request,
        settings=settings,
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
        settings=settings,
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
        settings=settings,
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
        settings=settings,
        scope="escalation_message",
        limit=settings.escalation_message_daily_limit_per_ip,
        enabled=settings.rate_limiting_enabled,
    )


def _enforce_daily_rate_limit(
    *,
    request: Request,
    settings: Settings,
    scope: str,
    limit: int,
    enabled: bool,
) -> None:
    if not enabled:
        return

    identifier = client_identifier_from_request(request)
    try:
        build_rate_limiter(settings).check(
            scope=scope,
            identifier=identifier,
            limit=limit,
        )
    except RateLimitStoreError:
        get_rate_limiter().check(scope=scope, identifier=identifier, limit=limit)
    except RateLimitExceeded as exc:
        raise _rate_limit_http_exception() from exc


def _rate_limit_http_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Daily request limit reached. Please try again later.",
    )
