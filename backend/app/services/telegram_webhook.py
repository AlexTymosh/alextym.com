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

        handoff_id = _extract_handoff_id(message)
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


def _is_owner_message(message: TelegramMessage, owner_chat_id: str) -> bool:
    return str(message.chat.id) == owner_chat_id


def _normalise_reply_text(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(text.strip().split())[:MAX_TELEGRAM_REPLY_CHARS]


def _extract_handoff_id(message: TelegramMessage) -> str | None:
    reply_to_message = message.reply_to_message
    if reply_to_message is None or not reply_to_message.text:
        return None

    match = HANDOFF_ID_PATTERN.search(reply_to_message.text)
    return match.group(1).lower() if match else None
