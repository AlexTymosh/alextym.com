import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.config import Settings
from app.schemas.escalation import EscalationRequest, EscalationResponse
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    EscalationSessionRecord,
    EscalationSessionStore,
    EscalationSessionStoreError,
    build_escalation_session_store,
)
from app.services.telegram import TelegramBotClient, TelegramDeliveryError


class EscalationConfigurationError(Exception):
    pass


class EscalationDeliveryError(Exception):
    pass


class EscalationNotFoundError(Exception):
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
        stream_poll_interval_seconds: float = 1.0,
        stream_heartbeat_interval_seconds: float = 15.0,
    ) -> None:
        self._notifier = notifier
        self._session_store = session_store
        self._session_ttl_seconds = session_ttl_seconds
        self._stream_poll_interval_seconds = stream_poll_interval_seconds
        self._stream_heartbeat_interval_seconds = stream_heartbeat_interval_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "EscalationService":
        configured_values = (
            settings.telegram_bot_token,
            settings.telegram_owner_chat_id,
        )
        is_configured = all(configured_values)
        has_partial_config = any(configured_values)

        session_store = build_escalation_session_store(settings)

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

    async def ensure_stream_available(self, handoff_id: str) -> None:
        if self._session_store is None:
            raise EscalationConfigurationError("Escalation session storage is not configured.")

        session_record = await self._get_session(handoff_id)
        if session_record is None or _is_expired(session_record):
            raise EscalationNotFoundError("Escalation session was not found.")

    async def stream_alex_messages(
        self,
        handoff_id: str,
        *,
        after_message_id: str | None = None,
    ) -> AsyncIterator[str]:
        if self._session_store is None:
            raise EscalationConfigurationError("Escalation session storage is not configured.")

        seen_message_ids: set[str] = set()
        if after_message_id:
            initial_record = await self._get_session(handoff_id)
            if initial_record is None or _is_expired(initial_record):
                yield self.sse_event("closed", {"reason": "session_expired"})
                return
            seen_message_ids.update(_message_ids_through(initial_record, after_message_id))

        yield self.sse_event("meta", {"handoff_id": handoff_id, "status": "connected"})

        next_heartbeat_at = (
            asyncio.get_running_loop().time() + self._stream_heartbeat_interval_seconds
        )

        while True:
            session_record = await self._get_session(handoff_id)
            if session_record is None or _is_expired(session_record):
                yield self.sse_event("closed", {"reason": "session_expired"})
                return

            for message in session_record.messages:
                message_id = message.get("id", "")
                if not message_id or message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)
                yield self.sse_event("message", message, event_id=message_id)

            current_time = asyncio.get_running_loop().time()
            if current_time >= next_heartbeat_at:
                yield ": heartbeat\n\n"
                next_heartbeat_at = current_time + self._stream_heartbeat_interval_seconds

            await asyncio.sleep(self._stream_poll_interval_seconds)

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

    async def _get_session(self, handoff_id: str) -> EscalationSessionRecord | None:
        if self._session_store is None:
            raise EscalationConfigurationError("Escalation session storage is not configured.")

        try:
            return await self._session_store.get(handoff_id)
        except EscalationSessionStoreError as exc:
            raise EscalationDeliveryError("Escalation session could not be read.") from exc

    async def _delete_session_if_created(
        self,
        session_record: EscalationSessionRecord | None,
    ) -> None:
        if session_record is None or self._session_store is None:
            return

        with suppress(EscalationSessionStoreError):
            await self._session_store.delete(session_record.handoff_id)

    @staticmethod
    def sse_event(event: str, data: dict[str, Any], *, event_id: str | None = None) -> str:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        lines = []
        if event_id:
            lines.append(f"id: {event_id}")
        lines.extend([f"event: {event}", f"data: {payload}"])
        return "\n".join(lines) + "\n\n"


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


def _message_ids_through(
    session_record: EscalationSessionRecord,
    after_message_id: str,
) -> set[str]:
    message_ids: set[str] = set()
    for message in session_record.messages:
        message_id = message.get("id", "")
        if not message_id:
            continue
        message_ids.add(message_id)
        if message_id == after_message_id:
            break
    else:
        return set()

    return message_ids


def _is_expired(session_record: EscalationSessionRecord) -> bool:
    try:
        expires_at = datetime.fromisoformat(session_record.expires_at)
    except ValueError:
        return True

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    return expires_at <= datetime.now(UTC)
