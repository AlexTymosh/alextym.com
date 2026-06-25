from typing import Any

from fastapi.testclient import TestClient

from app.api.telegram import get_telegram_webhook_service
from app.core.config import Settings, get_settings
from app.main import app
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_CONNECTED,
    EscalationSessionRecord,
    EscalationSessionStoreError,
)
from app.services.telegram_webhook import TelegramWebhookService

client = TestClient(app)

TEST_HANDOFF_ID = "hnd_" + "a" * 32
TEST_SECRET = "test-secret"
VALID_SECRET_HEADERS = {"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET}


def valid_update(
    *,
    chat_id: int = 123456789,
    text: str = "Hello from Alex",
    reply_text: str | None = "default",
) -> dict[str, object]:
    message: dict[str, object] = {
        "message_id": 200,
        "chat": {"id": chat_id, "type": "private"},
        "text": text,
    }
    if reply_text is not None:
        message["reply_to_message"] = {
            "message_id": 100,
            "chat": {"id": chat_id, "type": "private"},
            "text": reply_text
            if reply_text != "default"
            else f"New handoff request from alextym.com\nHandoff ID: {TEST_HANDOFF_ID}",
        }

    return {"update_id": 1, "message": message}


def callback_update(
    callback_data: str,
    *,
    chat_id: int = 123456789,
) -> dict[str, object]:
    return {
        "update_id": 1,
        "callback_query": {
            "id": "callback-1",
            "from": {"id": chat_id, "is_bot": False, "first_name": "Owner"},
            "message": {
                "message_id": 100,
                "chat": {"id": chat_id, "type": "private"},
                "text": f"New handoff request from alextym.com\nRef: {TEST_HANDOFF_ID}",
            },
            "data": callback_data,
        },
    }


def quick_reply_confirmation_text(content: str) -> str:
    return (
        "\u2705 <b>Sent to website chat</b>\n\n"
        f"<blockquote>{content}</blockquote>\n\n"
        f"<code>Ref: {TEST_HANDOFF_ID}</code>"
    )


def close_confirmation_text() -> str:
    return (
        "\u2705 <b>Handoff closed</b>\n\n"
        "The website visitor was notified that the conversation was closed.\n\n"
        f"<code>Ref: {TEST_HANDOFF_ID}</code>"
    )


def manual_reply_prompt_text() -> str:
    return (
        "\u270d\ufe0f <b>Manual reply</b>\n\n"
        "Reply to this message with your custom answer.\n"
        "Your reply will be sent to the website chat.\n\n"
        f"<code>Ref: {TEST_HANDOFF_ID}</code>"
    )


class FakeEscalationSessionStore:
    def __init__(self) -> None:
        self.appended_messages: list[tuple[str, str]] = []
        self.closed_handoff_ids: list[tuple[str, str | None]] = []

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        self.appended_messages.append((handoff_id, content))
        return EscalationSessionRecord(
            handoff_id=handoff_id,
            state=ESCALATION_SESSION_STATE_CONNECTED,
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-01T02:00:00+00:00",
            transcript=[],
            messages=[
                {
                    "id": "msg_test",
                    "role": "alex",
                    "content": content,
                    "created_at": "2026-01-01T00:01:00+00:00",
                }
            ],
        )

    async def close(
        self,
        handoff_id: str,
        *,
        close_message: str | None = None,
    ) -> EscalationSessionRecord | None:
        self.closed_handoff_ids.append((handoff_id, close_message))
        messages = []
        if close_message:
            messages.append(
                {
                    "id": "msg_closed",
                    "role": "alex",
                    "content": close_message,
                    "created_at": "2026-01-01T00:01:00+00:00",
                }
            )
        return EscalationSessionRecord(
            handoff_id=handoff_id,
            state=ESCALATION_SESSION_STATE_CLOSED,
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-01T02:00:00+00:00",
            transcript=[],
            messages=messages,
        )


class FailingEscalationSessionStore:
    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("redis failed")

    async def close(
        self,
        handoff_id: str,
        *,
        close_message: str | None = None,
    ) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("redis failed")


class FakeCallbackAcknowledger:
    def __init__(self) -> None:
        self.callback_answers: list[tuple[str, str | None, bool]] = []
        self.sent_messages: list[tuple[str, str | None, dict[str, object] | None]] = []

    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        self.callback_answers.append((callback_query_id, text, show_alert))

    async def send_message(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: dict[str, object] | None = None,
    ) -> None:
        self.sent_messages.append((text, parse_mode, reply_markup))


def use_webhook_service(
    store: Any,
    *,
    callback_acknowledger: FakeCallbackAcknowledger | None = None,
) -> None:
    app.dependency_overrides[get_telegram_webhook_service] = lambda: TelegramWebhookService(
        owner_chat_id="123456789",
        session_store=store,
        callback_acknowledger=callback_acknowledger or FakeCallbackAcknowledger(),
    )


def use_test_settings(*, telegram_webhook_secret: str = TEST_SECRET) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(
        telegram_webhook_secret=telegram_webhook_secret
    )


def _settings(*, telegram_webhook_secret: str = TEST_SECRET) -> Settings:
    return Settings(
        app_name="test",
        environment="test",
        frontend_origin="http://localhost:3000",
        openai_api_key="",
        openai_model="gpt-5-mini",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=1536,
        openai_max_output_tokens=600,
        openai_reasoning_effort="low",
        qdrant_url="",
        qdrant_api_key="",
        qdrant_collection="alex_public_knowledge",
        rag_top_k=6,
        rag_score_threshold=0.4,
        resend_api_key="",
        contact_target_email="",
        contact_from_email="",
        rate_limiting_enabled=True,
        chat_daily_limit_per_ip=50,
        contact_daily_limit_per_ip=5,
        telegram_owner_chat_id="123456789",
        telegram_webhook_secret=telegram_webhook_secret,
    )
