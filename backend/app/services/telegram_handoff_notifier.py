from app.core.config import Settings
from app.schemas.escalation import EscalationMessageRequest, EscalationRequest
from app.services.escalation_errors import EscalationDeliveryError
from app.services.escalation_notifier import (
    EscalationNotifier,
    NoopEscalationNotifier,
)
from app.services.telegram import TelegramBotClient, TelegramDeliveryError
from app.services.telegram_handoff_messages import (
    build_telegram_control_message,
    build_telegram_handoff_reply_markup,
    build_telegram_transcript_filename,
    build_telegram_transcript_message,
    build_telegram_user_message_notification,
)


class TelegramEscalationNotifier:
    def __init__(self, *, telegram_client: TelegramBotClient) -> None:
        self._telegram_client = telegram_client

    async def _send_operator_control_message(
        self,
        text: str,
        *,
        handoff_id: str,
    ) -> None:
        await self._telegram_client.send_message(
            text,
            parse_mode="HTML",
            reply_markup=build_telegram_handoff_reply_markup(handoff_id),
        )

    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        try:
            if handoff_id:
                await self._send_operator_control_message(
                    build_telegram_control_message(
                        escalation_request,
                        handoff_id=handoff_id,
                    ),
                    handoff_id=handoff_id,
                )
                await self._telegram_client.send_text_document(
                    build_telegram_transcript_message(
                        escalation_request,
                        handoff_id=handoff_id,
                    ),
                    filename=build_telegram_transcript_filename(handoff_id),
                )
                return

            await self._telegram_client.send_message(
                build_telegram_transcript_message(
                    escalation_request,
                    handoff_id=None,
                )
            )
        except TelegramDeliveryError as exc:
            raise EscalationDeliveryError(
                "Escalation notification could not be delivered."
            ) from exc

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        try:
            await self._send_operator_control_message(
                build_telegram_user_message_notification(
                    message_request,
                    handoff_id=handoff_id,
                ),
                handoff_id=handoff_id,
            )
        except TelegramDeliveryError as exc:
            raise EscalationDeliveryError(
                "Escalation user message could not be delivered."
            ) from exc


def build_escalation_notifier(settings: Settings) -> EscalationNotifier | None:
    configured_values = (
        settings.telegram_bot_token,
        settings.telegram_owner_chat_id,
    )
    is_configured = all(configured_values)
    has_partial_config = any(configured_values)

    if is_configured:
        return TelegramEscalationNotifier(
            telegram_client=TelegramBotClient(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_owner_chat_id,
            )
        )

    if settings.environment in {"local", "test"} and not has_partial_config:
        return NoopEscalationNotifier()

    return None
