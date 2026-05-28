from datetime import UTC, datetime
from typing import Protocol

from app.core.config import Settings
from app.schemas.escalation import EscalationRequest, EscalationResponse
from app.services.telegram import TelegramBotClient, TelegramDeliveryError


class EscalationConfigurationError(Exception):
    pass


class EscalationDeliveryError(Exception):
    pass


class EscalationNotifier(Protocol):
    async def notify(self, escalation_request: EscalationRequest) -> None:
        pass


class NoopEscalationNotifier:
    def __init__(self) -> None:
        self.sent_requests: list[EscalationRequest] = []

    async def notify(self, escalation_request: EscalationRequest) -> None:
        self.sent_requests.append(escalation_request)


class TelegramEscalationNotifier:
    def __init__(self, *, telegram_client: TelegramBotClient) -> None:
        self._telegram_client = telegram_client

    async def notify(self, escalation_request: EscalationRequest) -> None:
        try:
            await self._telegram_client.send_message(
                _build_telegram_notification(escalation_request)
            )
        except TelegramDeliveryError as exc:
            raise EscalationDeliveryError(
                "Escalation notification could not be delivered."
            ) from exc


class EscalationService:
    def __init__(self, *, notifier: EscalationNotifier | None) -> None:
        self._notifier = notifier

    @classmethod
    def from_settings(cls, settings: Settings) -> "EscalationService":
        configured_values = (
            settings.telegram_bot_token,
            settings.telegram_owner_chat_id,
        )
        is_configured = all(configured_values)
        has_partial_config = any(configured_values)

        if is_configured:
            return cls(
                notifier=TelegramEscalationNotifier(
                    telegram_client=TelegramBotClient(
                        bot_token=settings.telegram_bot_token,
                        chat_id=settings.telegram_owner_chat_id,
                    )
                )
            )

        if settings.environment in {"local", "test"} and not has_partial_config:
            return cls(notifier=NoopEscalationNotifier())

        return cls(notifier=None)

    async def submit(self, escalation_request: EscalationRequest) -> EscalationResponse:
        if escalation_request.is_honeypot_filled:
            return EscalationResponse()

        if self._notifier is None:
            raise EscalationConfigurationError("Escalation notifications are not configured.")

        await self._notifier.notify(escalation_request)
        return EscalationResponse()


def _build_telegram_notification(escalation_request: EscalationRequest) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    transcript_lines = []
    for item in escalation_request.transcript:
        role = "User" if item.role == "user" else "Assistant"
        transcript_lines.append(f"{role}: {item.content}")

    return "\n\n".join(
        [
            "New handoff request from alextym.com",
            f"Created at: {created_at}",
            f"Reason: {escalation_request.reason}",
            "Transcript:\n" + "\n\n".join(transcript_lines),
            "No email or phone number was shared unless the visitor typed it manually.",
        ]
    )
