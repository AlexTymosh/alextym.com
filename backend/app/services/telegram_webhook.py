import re
from dataclasses import dataclass
from html import escape
from typing import Literal, Protocol

from app.core.config import Settings
from app.repositories.escalation_session_store import (
    EscalationSessionStore,
    EscalationSessionStoreError,
)
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage, TelegramUpdate
from app.services.escalation_sessions import build_escalation_session_store
from app.services.handoff_copy import (
    CONTACT_QUICK_REPLY as CONTACT_QUICK_REPLY,
    HANDOFF_CLOSED_AFTER_NO_RESPONSE_REPLY as CLOSE_HANDOFF_REPLY,
    READING_QUICK_REPLY as READING_QUICK_REPLY,
    STILL_THERE_QUICK_REPLY as STILL_THERE_QUICK_REPLY,
    quick_reply_for_callback_action,
)
from app.services.telegram import TelegramBotClient, TelegramDeliveryError

HANDOFF_ID_PATTERN = re.compile(r"\b(hnd_[a-f0-9]{32})\b", re.IGNORECASE)
CLOSE_COMMAND_PATTERN = re.compile(
    r"^\s*/close(?:@\w+)?(?:\s+(hnd_[a-f0-9]{32}))?\s*$",
    re.IGNORECASE,
)
CALLBACK_DATA_PATTERN = re.compile(
    r"^handoff:(reply|close|reading|contact|still):(hnd_[a-f0-9]{32})$",
    re.IGNORECASE,
)
MAX_TELEGRAM_REPLY_CHARS = 2000
REPLY_HELP_CALLBACK_TEXT = "Manual reply mode opened."
ACTION_SENT_CALLBACK_TEXT = "Sent to the website chat."
ACTION_CLOSED_CALLBACK_TEXT = "Closed and notified the website visitor."
ACTION_UNAVAILABLE_CALLBACK_TEXT = "This handoff is no longer available."
ACTION_IGNORED_CALLBACK_TEXT = "This Telegram action is not supported."


class TelegramWebhookConfigurationError(Exception):
    pass


class TelegramWebhookProcessingError(Exception):
    pass


class TelegramCallbackAcknowledger(Protocol):
    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        pass

    async def send_message(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: dict[str, object] | None = None,
    ) -> None:
        pass


@dataclass(frozen=True)
class TelegramWebhookResult:
    status: Literal["ok", "ignored"]
    handoff_id: str | None = None


@dataclass(frozen=True)
class TelegramCallbackAction:
    action: Literal["reply", "close", "reading", "contact", "still"]
    handoff_id: str


class TelegramWebhookService:
    def __init__(
        self,
        *,
        owner_chat_id: str,
        session_store: EscalationSessionStore | None,
        callback_acknowledger: TelegramCallbackAcknowledger | None = None,
    ) -> None:
        self._owner_chat_id = owner_chat_id.strip()
        self._session_store = session_store
        self._callback_acknowledger = callback_acknowledger

    @classmethod
    def from_settings(cls, settings: Settings) -> "TelegramWebhookService":
        callback_acknowledger: TelegramCallbackAcknowledger | None = None
        if settings.telegram_bot_token:
            callback_acknowledger = TelegramBotClient(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_owner_chat_id,
            )

        return cls(
            owner_chat_id=settings.telegram_owner_chat_id,
            session_store=build_escalation_session_store(settings),
            callback_acknowledger=callback_acknowledger,
        )

    async def handle_update(self, update: TelegramUpdate) -> TelegramWebhookResult:
        if not self._owner_chat_id or self._session_store is None:
            raise TelegramWebhookConfigurationError("Telegram webhook is not configured.")

        if update.callback_query is not None:
            return await self._handle_callback_query(update.callback_query)

        message = update.message
        if message is None or not _is_owner_message(message, self._owner_chat_id):
            return TelegramWebhookResult(status="ignored")

        reply_text = _normalise_reply_text(message.text)
        if not reply_text:
            return TelegramWebhookResult(status="ignored")

        if _is_close_command(reply_text):
            return await self._handle_close_command(message, reply_text)

        if reply_text.startswith("/"):
            return TelegramWebhookResult(status="ignored")

        handoff_id = _extract_handoff_id_from_reply(message)
        if handoff_id is None:
            return TelegramWebhookResult(status="ignored")

        return await self._append_owner_message(handoff_id, reply_text)

    async def _handle_callback_query(
        self,
        callback_query: TelegramCallbackQuery,
    ) -> TelegramWebhookResult:
        if not _is_owner_callback(callback_query, self._owner_chat_id):
            return TelegramWebhookResult(status="ignored")

        callback_action = _parse_callback_data(callback_query.data)
        if callback_action is None:
            await self._answer_callback_query(
                callback_query.id,
                text=ACTION_IGNORED_CALLBACK_TEXT,
            )
            return TelegramWebhookResult(status="ignored")

        if callback_action.action == "reply":
            await self._answer_callback_query(
                callback_query.id,
                text=REPLY_HELP_CALLBACK_TEXT,
            )
            await self._send_operator_confirmation(
                _build_manual_reply_prompt_message(
                    handoff_id=callback_action.handoff_id,
                ),
                reply_markup=_build_manual_reply_force_reply_markup(),
            )
            return TelegramWebhookResult(
                status="ok",
                handoff_id=callback_action.handoff_id,
            )

        if callback_action.action == "close":
            return await self._close_from_callback(callback_query, callback_action.handoff_id)

        quick_reply = quick_reply_for_callback_action(callback_action.action)
        if quick_reply is None:
            await self._answer_callback_query(
                callback_query.id,
                text=ACTION_IGNORED_CALLBACK_TEXT,
            )
            return TelegramWebhookResult(status="ignored")

        result = await self._append_owner_message(callback_action.handoff_id, quick_reply)
        await self._answer_callback_query(
            callback_query.id,
            text=ACTION_SENT_CALLBACK_TEXT
            if result.status == "ok"
            else ACTION_UNAVAILABLE_CALLBACK_TEXT,
            show_alert=result.status != "ok",
        )
        if result.status == "ok":
            await self._send_operator_confirmation(
                _build_quick_reply_confirmation_message(
                    handoff_id=callback_action.handoff_id,
                    content=quick_reply,
                )
            )
        return result

    async def _close_from_callback(
        self,
        callback_query: TelegramCallbackQuery,
        handoff_id: str,
    ) -> TelegramWebhookResult:
        try:
            closed_session = await self._session_store.close(
                handoff_id,
                close_message=CLOSE_HANDOFF_REPLY,
            )
        except EscalationSessionStoreError as exc:
            raise TelegramWebhookProcessingError("Telegram handoff could not close.") from exc

        await self._answer_callback_query(
            callback_query.id,
            text=ACTION_CLOSED_CALLBACK_TEXT
            if closed_session is not None
            else ACTION_UNAVAILABLE_CALLBACK_TEXT,
            show_alert=closed_session is None,
        )

        if closed_session is None:
            return TelegramWebhookResult(status="ignored", handoff_id=handoff_id)

        await self._send_operator_confirmation(
            _build_close_confirmation_message(handoff_id=handoff_id)
        )
        return TelegramWebhookResult(status="ok", handoff_id=handoff_id)

    async def _handle_close_command(
        self,
        message: TelegramMessage,
        text: str,
    ) -> TelegramWebhookResult:
        handoff_id = _extract_handoff_id_from_close_command(text)
        if handoff_id is None:
            handoff_id = _extract_handoff_id_from_reply(message)
        if handoff_id is None:
            return TelegramWebhookResult(status="ignored")

        try:
            closed_session = await self._session_store.close(handoff_id)
        except EscalationSessionStoreError as exc:
            raise TelegramWebhookProcessingError("Telegram handoff could not close.") from exc

        if closed_session is None:
            return TelegramWebhookResult(status="ignored", handoff_id=handoff_id)

        return TelegramWebhookResult(status="ok", handoff_id=handoff_id)

    async def _append_owner_message(
        self,
        handoff_id: str,
        content: str,
    ) -> TelegramWebhookResult:
        try:
            updated_session = await self._session_store.append_alex_message(
                handoff_id,
                content,
            )
        except EscalationSessionStoreError as exc:
            raise TelegramWebhookProcessingError("Telegram reply could not be stored.") from exc

        if updated_session is None:
            return TelegramWebhookResult(status="ignored", handoff_id=handoff_id)

        return TelegramWebhookResult(status="ok", handoff_id=handoff_id)

    async def _send_operator_confirmation(
        self,
        text: str,
        *,
        reply_markup: dict[str, object] | None = None,
    ) -> None:
        if self._callback_acknowledger is None:
            return

        try:
            await self._callback_acknowledger.send_message(
                text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except TelegramDeliveryError:
            # The website action has already been applied. Do not fail the webhook
            # and risk Telegram retrying the callback and duplicating the action.
            return

    async def _answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        if self._callback_acknowledger is None:
            raise TelegramWebhookConfigurationError(
                "Telegram callback acknowledgement is not configured."
            )

        try:
            await self._callback_acknowledger.answer_callback_query(
                callback_query_id,
                text=text,
                show_alert=show_alert,
            )
        except TelegramDeliveryError as exc:
            raise TelegramWebhookProcessingError(
                "Telegram callback could not be acknowledged."
            ) from exc


def _build_manual_reply_prompt_message(*, handoff_id: str) -> str:
    return "\n".join(
        [
            "✍️ <b>Manual reply</b>",
            "",
            "Reply to this message with your custom answer.",
            "Your reply will be sent to the website chat.",
            "",
            f"<code>Ref: {escape(handoff_id)}</code>",
        ]
    )


def _build_manual_reply_force_reply_markup() -> dict[str, object]:
    return {
        "force_reply": True,
        "selective": True,
        "input_field_placeholder": "Type the website chat reply here...",
    }


def _build_quick_reply_confirmation_message(*, handoff_id: str, content: str) -> str:
    return "\n".join(
        [
            "✅ <b>Sent to website chat</b>",
            "",
            f"<blockquote>{escape(content)}</blockquote>",
            "",
            f"<code>Ref: {escape(handoff_id)}</code>",
        ]
    )


def _build_close_confirmation_message(*, handoff_id: str) -> str:
    return "\n".join(
        [
            "✅ <b>Handoff closed</b>",
            "",
            "The website visitor was notified that the conversation was closed.",
            "",
            f"<code>Ref: {escape(handoff_id)}</code>",
        ]
    )


def _is_owner_message(message: TelegramMessage, owner_chat_id: str) -> bool:
    return str(message.chat.id) == owner_chat_id


def _is_owner_callback(
    callback_query: TelegramCallbackQuery,
    owner_chat_id: str,
) -> bool:
    message = callback_query.message
    if message is None or message.chat is None:
        return False
    return str(message.chat.id) == owner_chat_id


def _normalise_reply_text(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(text.strip().split())[:MAX_TELEGRAM_REPLY_CHARS]


def _is_close_command(text: str) -> bool:
    return CLOSE_COMMAND_PATTERN.match(text) is not None


def _extract_handoff_id_from_close_command(text: str) -> str | None:
    match = CLOSE_COMMAND_PATTERN.match(text)
    if not match:
        return None
    handoff_id = match.group(1)
    return handoff_id.lower() if handoff_id else None


def _extract_handoff_id_from_reply(message: TelegramMessage) -> str | None:
    reply_to_message = message.reply_to_message
    if reply_to_message is None or not reply_to_message.text:
        return None

    match = HANDOFF_ID_PATTERN.search(reply_to_message.text)
    return match.group(1).lower() if match else None


def _parse_callback_data(data: str | None) -> TelegramCallbackAction | None:
    if not data:
        return None

    match = CALLBACK_DATA_PATTERN.match(data.strip())
    if not match:
        return None

    return TelegramCallbackAction(
        action=match.group(1).lower(),
        handoff_id=match.group(2).lower(),
    )
