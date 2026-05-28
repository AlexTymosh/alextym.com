import re
from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.schemas.telegram import TelegramMessage, TelegramUpdate
from app.services.escalation_sessions import (
    EscalationSessionStore,
    EscalationSessionStoreError,
    build_escalation_session_store,
)

HANDOFF_ID_PATTERN = re.compile(r"\b(hnd_[a-f0-9]{32})\b", re.IGNORECASE)
CLOSE_COMMAND_PATTERN = re.compile(
    r"^\s*/close(?:@\w+)?(?:\s+(hnd_[a-f0-9]{32}))?\s*$",
    re.IGNORECASE,
)
MAX_TELEGRAM_REPLY_CHARS = 2000


class TelegramWebhookConfigurationError(Exception):
    pass


class TelegramWebhookProcessingError(Exception):
    pass


@dataclass(frozen=True)
class TelegramWebhookResult:
    status: Literal["ok", "ignored"]
    handoff_id: str | None = None


class TelegramWebhookService:
    def __init__(
        self,
        *,
        owner_chat_id: str,
        session_store: EscalationSessionStore | None,
    ) -> None:
        self._owner_chat_id = owner_chat_id.strip()
        self._session_store = session_store

    @classmethod
    def from_settings(cls, settings: Settings) -> "TelegramWebhookService":
        return cls(
            owner_chat_id=settings.telegram_owner_chat_id,
            session_store=build_escalation_session_store(settings),
        )

    async def handle_update(self, update: TelegramUpdate) -> TelegramWebhookResult:
        if not self._owner_chat_id or self._session_store is None:
            raise TelegramWebhookConfigurationError("Telegram webhook is not configured.")

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

        try:
            updated_session = await self._session_store.append_alex_message(
                handoff_id,
                reply_text,
            )
        except EscalationSessionStoreError as exc:
            raise TelegramWebhookProcessingError("Telegram reply could not be stored.") from exc

        if updated_session is None:
            return TelegramWebhookResult(status="ignored", handoff_id=handoff_id)

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


def _is_owner_message(message: TelegramMessage, owner_chat_id: str) -> bool:
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
