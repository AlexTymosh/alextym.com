from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.telegram import TelegramUpdate, TelegramWebhookResponse
from app.services.telegram_webhook import (
    TelegramWebhookConfigurationError,
    TelegramWebhookProcessingError,
    TelegramWebhookResult,
    TelegramWebhookService,
)

router = APIRouter(tags=["telegram"])


def get_telegram_webhook_service(
    settings: Settings = Depends(get_settings),
) -> TelegramWebhookService:
    return TelegramWebhookService.from_settings(settings)


@router.post(
    "/telegram/webhook",
    response_model=TelegramWebhookResponse,
    response_model_exclude_none=True,
)
async def telegram_webhook(
    update: TelegramUpdate,
    telegram_secret_token: Annotated[
        str | None,
        Header(alias="X-Telegram-Bot-Api-Secret-Token"),
    ] = None,
    settings: Settings = Depends(get_settings),
    service: TelegramWebhookService = Depends(get_telegram_webhook_service),
) -> TelegramWebhookResponse:
    _verify_telegram_secret_token(settings, telegram_secret_token)

    try:
        result = await service.handle_update(update)
    except TelegramWebhookConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook is not configured.",
        ) from exc
    except TelegramWebhookProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telegram reply could not be processed.",
        ) from exc

    return _to_response(result)


def _verify_telegram_secret_token(
    settings: Settings,
    telegram_secret_token: str | None,
) -> None:
    if not settings.telegram_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook is not configured.",
        )

    if telegram_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret.",
        )


def _to_response(result: TelegramWebhookResult) -> TelegramWebhookResponse:
    return TelegramWebhookResponse(status=result.status, handoff_id=result.handoff_id)
