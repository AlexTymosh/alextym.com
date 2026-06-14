import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from html import escape
from typing import Any, Protocol

from app.core.config import Settings
from app.schemas.escalation import (
    EscalationCloseResponse,
    EscalationMessageRequest,
    EscalationMessageResponse,
    EscalationRequest,
    EscalationResponse,
)
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    EscalationSessionRecord,
    EscalationSessionStore,
    EscalationSessionStoreError,
    build_escalation_session_store,
)
from app.services.handoff_availability import (
    AlwaysAvailableHandoffAvailabilityChecker,
    HandoffAvailabilityChecker,
    build_handoff_availability_checker,
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

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        pass


class NoopEscalationNotifier:
    def __init__(self) -> None:
        self.sent_requests: list[EscalationRequest] = []
        self.sent_handoff_ids: list[str | None] = []
        self.sent_message_requests: list[EscalationMessageRequest] = []
        self.sent_message_handoff_ids: list[str] = []

    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        self.sent_requests.append(escalation_request)
        self.sent_handoff_ids.append(handoff_id)

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        self.sent_message_requests.append(message_request)
        self.sent_message_handoff_ids.append(handoff_id)


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
            if handoff_id:
                await self._telegram_client.send_message(
                    _build_telegram_control_message(
                        escalation_request,
                        handoff_id=handoff_id,
                    ),
                    parse_mode="HTML",
                )
                await self._telegram_client.send_text_document(
                    _build_telegram_transcript_message(
                        escalation_request,
                        handoff_id=handoff_id,
                    ),
                    filename=_build_telegram_transcript_filename(handoff_id),
                )
                return

            await self._telegram_client.send_message(
                _build_telegram_transcript_message(
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
            await self._telegram_client.send_message(
                _build_telegram_user_message_notification(
                    message_request,
                    handoff_id=handoff_id,
                )
            )
        except TelegramDeliveryError as exc:
            raise EscalationDeliveryError(
                "Escalation user message could not be delivered."
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
        configured_values = (
            settings.telegram_bot_token,
            settings.telegram_owner_chat_id,
        )
        is_configured = all(configured_values)
        has_partial_config = any(configured_values)

        session_store = build_escalation_session_store(settings)
        availability_checker = build_handoff_availability_checker(settings)

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
                availability_checker=availability_checker,
            )

        if settings.environment in {"local", "test"} and not has_partial_config:
            return cls(
                notifier=NoopEscalationNotifier(),
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

        self.ensure_handoff_available()

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
    ) -> AsyncIterator[str]:
        if self._session_store is None:
            raise EscalationConfigurationError("Escalation session storage is not configured.")

        seen_message_ids: set[str] = set()
        if after_message_id:
            initial_record = await self._get_session(handoff_id)
            if initial_record is None or _is_expired(initial_record):
                yield self.sse_event("closed", {"reason": "session_expired"})
                return
            if initial_record.state == ESCALATION_SESSION_STATE_CLOSED:
                yield self.sse_event("closed", {"reason": "session_closed"})
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
            if session_record.state == ESCALATION_SESSION_STATE_CLOSED:
                yield self.sse_event("closed", {"reason": "session_closed"})
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
    def sse_event(
        event: str,
        data: dict[str, Any],
        *,
        event_id: str | None = None,
    ) -> str:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        lines = []
        if event_id:
            lines.append(f"id: {event_id}")
        lines.extend([f"event: {event}", f"data: {payload}"])
        return "\n".join(lines) + "\n\n"


def _build_telegram_control_message(
    escalation_request: EscalationRequest,
    *,
    handoff_id: str,
) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    created_date, created_time, created_offset = _split_iso_datetime(created_at)
    last_user_message = _last_user_message(escalation_request)
    lines = [
        "<b>🚨 New handoff request — alextym.com</b>",
        "",
        "<b>Last user message</b>",
        f"<blockquote>{_html_escape(_clip_control_text(last_user_message))}</blockquote>",
        "",
        "<b>Created at</b>",
        f"<code>{_html_escape(created_date)}</code>",
        f"<b>{_html_escape(created_time)}</b> {_html_escape(created_offset)}",
        "",
        f"<b>AI messages before handoff:</b> {_assistant_message_count(escalation_request)}",
        f"<b>Status:</b> {_telegram_status_label(ESCALATION_SESSION_STATE_WAITING_FOR_ALEX)}",
    ]

    if _should_show_handoff_reason(escalation_request.reason):
        lines.extend(
            [
                "",
                f"<b>Reason:</b> <code>{_html_escape(escalation_request.reason)}</code>",
            ]
        )

    lines.extend(
        [
            "",
            f"<code>Ref: {_html_escape(handoff_id)}</code>",
            "",
            "Reply to this Telegram message to answer the website chat.",
            "The full transcript is attached as a text file.",
            f"Fallback close command: <code>/close {_html_escape(handoff_id)}</code>",
        ]
    )
    return "\n".join(lines)


def _split_iso_datetime(value: str) -> tuple[str, str, str]:
    created_date, _, time_with_offset = value.partition("T")
    if "+" in time_with_offset:
        created_time, raw_offset = time_with_offset.split("+", 1)
        return created_date, created_time, f"+{raw_offset}"
    if "-" in time_with_offset[1:]:
        created_time, raw_offset = time_with_offset.rsplit("-", 1)
        return created_date, created_time, f"-{raw_offset}"
    return created_date, time_with_offset, "UTC"


def _build_telegram_transcript_message(
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
        "Handoff transcript from alextym.com",
        f"Created at: {created_at}",
        f"Reason: {escalation_request.reason}",
    ]
    if handoff_id:
        header_lines.append(f"Handoff ID: {handoff_id}")

    return "\n\n".join(
        [
            "\n".join(header_lines),
            "Transcript:\n" + "\n\n".join(transcript_lines),
            "No email or phone number was shared unless the visitor typed it manually.",
        ]
    )


def _build_telegram_transcript_filename(handoff_id: str) -> str:
    return f"handoff-transcript-{handoff_id}.txt"


def _build_telegram_user_message_notification(
    message_request: EscalationMessageRequest,
    *,
    handoff_id: str,
) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    return "\n\n".join(
        [
            "New visitor message from alextym.com",
            f"Created at: {created_at}\nHandoff ID: {handoff_id}",
            f"User: {message_request.content}",
            "Reply to this Telegram message to send your answer back to the chat.",
            f"Use /close {handoff_id} to close the handoff.",
        ]
    )


def _assistant_message_count(escalation_request: EscalationRequest) -> int:
    return sum(1 for item in escalation_request.transcript if item.role == "assistant")


def _should_show_handoff_reason(reason: str) -> bool:
    return reason != "user_requested_human"


def _telegram_status_label(state: str) -> str:
    if state == ESCALATION_SESSION_STATE_WAITING_FOR_ALEX:
        return "🔴 Waiting for first operator reply"
    if state == ESCALATION_SESSION_STATE_CLOSED:
        return "🟢 Closed"
    return _html_escape(state)


def _last_user_message(escalation_request: EscalationRequest) -> str:
    for item in reversed(escalation_request.transcript):
        if item.role == "user":
            return item.content
    return ""


def _html_escape(text: str) -> str:
    return escape(text or "No user message found.", quote=False)


def _clip_control_text(text: str, max_chars: int = 500) -> str:
    compact_text = " ".join(text.split())
    if len(compact_text) <= max_chars:
        return compact_text
    return compact_text[: max_chars - 1].rstrip() + "…"


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
