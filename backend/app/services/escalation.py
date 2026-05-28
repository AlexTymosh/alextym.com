from contextlib import suppress
from datetime import UTC, datetime
from typing import Protocol

from app.core.config import Settings
from app.schemas.escalation import EscalationRequest, EscalationResponse
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    EscalationSessionRecord,
    EscalationSessionStore,
    EscalationSessionStoreError,
    MisconfiguredEscalationSessionStore,
    UpstashRedisEscalationSessionStore,
)
from app.services.telegram import TelegramBotClient, TelegramDeliveryError


class EscalationConfigurationError(Exception):
    pass


class EscalationDeliveryError(Exception):
    pass


class EscalationNotifier(Protocol):
    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        pass


class NoopEscalationNotifier:
    def __init__(self) -> None:
        self.sent_requests: list[EscalationRequest] = []
        self.sent_handoff_ids: list[str | None] = []

    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        self.sent_requests.append(escalation_request)
        self.sent_handoff_ids.append(handoff_id)


class TelegramEscalationNotifier:
    def __init__(self, *, telegram_client: TelegramBotClient) -> None:
        self._telegram_client = telegram_client

    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        try:
            await self._telegram_client.send_message(
                _build_telegram_notification(escalation_request, handoff_id=handoff_id)
            )
        except TelegramDeliveryError as exc:
            raise EscalationDeliveryError(
                "Escalation notification could not be delivered."
            ) from exc


class EscalationService:
    def __init__(
        self,
        *,
        notifier: EscalationNotifier | None,
        session_store: EscalationSessionStore | None = None,
        session_ttl_seconds: int = 7200,
    ) -> None:
        self._notifier = notifier
        self._session_store = session_store
        self._session_ttl_seconds = session_ttl_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "EscalationService":
        configured_values = (
            settings.telegram_bot_token,
            settings.telegram_owner_chat_id,
        )
        is_configured = all(configured_values)
        has_partial_config = any(configured_values)

        session_store = _build_session_store(settings)

        if is_configured:
            return cls(
                notifier=TelegramEscalationNotifier(
                    telegram_client=TelegramBotClient(
                        bot_token=settings.telegram_bot_token,
                        chat_id=settings.telegram_owner_chat_id,
                    )
                ),
                session_store=session_store,
                session_ttl_seconds=settings.escalation_session_ttl_seconds,
            )

        if settings.environment in {"local", "test"} and not has_partial_config:
            return cls(
                notifier=NoopEscalationNotifier(),
                session_store=session_store,
                session_ttl_seconds=settings.escalation_session_ttl_seconds,
            )

        return cls(notifier=None, session_store=session_store)

    async def submit(self, escalation_request: EscalationRequest) -> EscalationResponse:
        if escalation_request.is_honeypot_filled:
            return EscalationResponse()

        if self._notifier is None:
            raise EscalationConfigurationError("Escalation notifications are not configured.")

        session_record = await self._create_session(escalation_request)

        try:
            await self._notifier.notify(
                escalation_request,
                handoff_id=session_record.handoff_id if session_record else None,
            )
        except EscalationDeliveryError:
            await self._delete_session_if_created(session_record)
            raise

        if session_record is None:
            return EscalationResponse()

        return EscalationResponse(
            status="ok",
            handoff_id=session_record.handoff_id,
            state=session_record.state,
            expires_in_seconds=self._session_ttl_seconds,
        )

    async def _create_session(
        self,
        escalation_request: EscalationRequest,
    ) -> EscalationSessionRecord | None:
        if self._session_store is None:
            return None

        try:
            return await self._session_store.create(
                escalation_request,
                ttl_seconds=self._session_ttl_seconds,
            )
        except EscalationSessionStoreError as exc:
            raise EscalationDeliveryError("Escalation session could not be stored.") from exc

    async def _delete_session_if_created(
        self,
        session_record: EscalationSessionRecord | None,
    ) -> None:
        if session_record is None or self._session_store is None:
            return

        with suppress(EscalationSessionStoreError):
            await self._session_store.delete(session_record.handoff_id)


def _build_session_store(settings: Settings) -> EscalationSessionStore | None:
    upstash_values = (
        settings.upstash_redis_rest_url,
        settings.upstash_redis_rest_token,
    )
    if all(upstash_values):
        return UpstashRedisEscalationSessionStore(
            rest_url=settings.upstash_redis_rest_url,
            rest_token=settings.upstash_redis_rest_token,
        )
    if any(upstash_values):
        return MisconfiguredEscalationSessionStore()

    return None


def _build_telegram_notification(
    escalation_request: EscalationRequest,
    *,
    handoff_id: str | None,
) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    transcript_lines = []
    for item in escalation_request.transcript:
        role = "User" if item.role == "user" else "Assistant"
        transcript_lines.append(f"{role}: {item.content}")

    header_lines = [
        "New handoff request from alextym.com",
        f"Created at: {created_at}",
        f"Reason: {escalation_request.reason}",
    ]
    if handoff_id:
        header_lines.append(f"Handoff ID: {handoff_id}")
        header_lines.append(f"State: {ESCALATION_SESSION_STATE_WAITING_FOR_ALEX}")

    return "\n\n".join(
        [
            "\n".join(header_lines),
            "Transcript:\n" + "\n\n".join(transcript_lines),
            "No email or phone number was shared unless the visitor typed it manually.",
        ]
    )
