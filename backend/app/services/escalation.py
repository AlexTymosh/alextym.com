import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime

from app.core.config import Settings
from app.repositories.escalation_session_store import (
    EscalationSessionStore,
    EscalationSessionStoreError,
)
from app.schemas.escalation import (
    EscalationCloseResponse,
    EscalationMessageRequest,
    EscalationMessageResponse,
    EscalationRequest,
    EscalationResponse,
)
from app.schemas.sse import ServerSentComment, ServerSentEvent, ServerSentStreamItem
from app.services.escalation_errors import (
    EscalationConfigurationError,
    EscalationDeliveryError,
    EscalationNotFoundError,
)
from app.services.escalation_notifier import (
    EscalationNotifier,
    NoopEscalationNotifier,
)
from app.services.telegram_handoff_notifier import (
    TelegramEscalationNotifier,
    build_escalation_notifier,
)
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_CLOSED,
    EscalationSessionRecord,
    build_escalation_session_store,
)
from app.services.escalation_session_state import build_initial_session_record
from app.services.handoff_availability import (
    AlwaysAvailableHandoffAvailabilityChecker,
    HandoffAvailabilityChecker,
    build_handoff_availability_checker,
)

__all__ = [
    "EscalationConfigurationError",
    "EscalationDeliveryError",
    "EscalationNotFoundError",
    "EscalationNotifier",
    "NoopEscalationNotifier",
    "TelegramEscalationNotifier",
    "EscalationService",
]


class EscalationService:
    def __init__(
        self,
        *,
        notifier: EscalationNotifier | None,
        session_store: EscalationSessionStore | None = None,
        session_ttl_seconds: int = 7200,
        stream_poll_interval_seconds: float = 1.0,
        stream_heartbeat_interval_seconds: float = 15.0,
        availability_checker: HandoffAvailabilityChecker | None = None,
    ) -> None:
        self._notifier = notifier
        self._session_store = session_store
        self._session_ttl_seconds = session_ttl_seconds
        self._stream_poll_interval_seconds = stream_poll_interval_seconds
        self._stream_heartbeat_interval_seconds = stream_heartbeat_interval_seconds
        self._availability_checker = (
            availability_checker or AlwaysAvailableHandoffAvailabilityChecker()
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "EscalationService":
        session_store = build_escalation_session_store(settings)
        availability_checker = build_handoff_availability_checker(settings)
        notifier = build_escalation_notifier(settings)

        if notifier is not None:
            return cls(
                notifier=notifier,
                session_store=session_store,
                session_ttl_seconds=settings.escalation_session_ttl_seconds,
                availability_checker=availability_checker,
            )

        return cls(
            notifier=None,
            session_store=session_store,
            availability_checker=availability_checker,
        )

    def ensure_handoff_available(self) -> None:
        self._availability_checker.ensure_available()

    async def submit(self, escalation_request: EscalationRequest) -> EscalationResponse:
        if escalation_request.is_honeypot_filled:
            return EscalationResponse()

        self.ensure_handoff_available()

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

    async def submit_user_message(
        self,
        handoff_id: str,
        message_request: EscalationMessageRequest,
    ) -> EscalationMessageResponse:
        if message_request.is_honeypot_filled:
            return EscalationMessageResponse()

        if self._notifier is None:
            raise EscalationConfigurationError("Escalation notifications are not configured.")
        if self._session_store is None:
            raise EscalationConfigurationError("Escalation session storage is not configured.")

        session_record = await self._get_session(handoff_id)
        if _is_unavailable_session(session_record):
            raise EscalationNotFoundError("Escalation session was not found.")

        await self._notifier.notify_user_message(message_request, handoff_id=handoff_id)
        return EscalationMessageResponse()

    async def close(self, handoff_id: str) -> EscalationCloseResponse:
        if self._session_store is None:
            raise EscalationConfigurationError("Escalation session storage is not configured.")

        try:
            session_record = await self._session_store.close(handoff_id)
        except EscalationSessionStoreError as exc:
            raise EscalationDeliveryError("Escalation session could not be closed.") from exc

        if session_record is None or _is_expired(session_record):
            raise EscalationNotFoundError("Escalation session was not found.")

        return EscalationCloseResponse(state=ESCALATION_SESSION_STATE_CLOSED)

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
    ) -> AsyncIterator[ServerSentStreamItem]:
        if self._session_store is None:
            raise EscalationConfigurationError("Escalation session storage is not configured.")

        seen_message_ids: set[str] = set()
        if after_message_id:
            initial_record = await self._get_session(handoff_id)
            if initial_record is None or _is_expired(initial_record):
                yield ServerSentEvent("closed", {"reason": "session_expired"})
                return
            seen_message_ids.update(_message_ids_through(initial_record, after_message_id))

        yield ServerSentEvent("meta", {"handoff_id": handoff_id, "status": "connected"})

        next_heartbeat_at = (
            asyncio.get_running_loop().time() + self._stream_heartbeat_interval_seconds
        )

        while True:
            session_record = await self._get_session(handoff_id)
            if session_record is None or _is_expired(session_record):
                yield ServerSentEvent("closed", {"reason": "session_expired"})
                return
            for message in session_record.messages:
                message_id = message.get("id", "")
                if not message_id or message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)
                yield ServerSentEvent("message", message, event_id=message_id)

            if session_record.state == ESCALATION_SESSION_STATE_CLOSED:
                yield ServerSentEvent("closed", {"reason": "session_closed"})
                return

            current_time = asyncio.get_running_loop().time()
            if current_time >= next_heartbeat_at:
                yield ServerSentComment("heartbeat")
                next_heartbeat_at = current_time + self._stream_heartbeat_interval_seconds

            await asyncio.sleep(self._stream_poll_interval_seconds)

    async def _create_session(
        self,
        escalation_request: EscalationRequest,
    ) -> EscalationSessionRecord | None:
        if self._session_store is None:
            return None

        session_record = build_initial_session_record(
            transcript=[
                {"role": item.role, "content": item.content}
                for item in escalation_request.transcript
            ],
            ttl_seconds=self._session_ttl_seconds,
        )

        try:
            return await self._session_store.create(
                session_record,
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


def _is_unavailable_session(session_record: EscalationSessionRecord | None) -> bool:
    return (
        session_record is None
        or _is_expired(session_record)
        or session_record.state == ESCALATION_SESSION_STATE_CLOSED
    )


def _is_expired(session_record: EscalationSessionRecord) -> bool:
    try:
        expires_at = datetime.fromisoformat(session_record.expires_at)
    except ValueError:
        return True

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    return expires_at <= datetime.now(UTC)
