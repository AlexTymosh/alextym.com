import pytest
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


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_telegram_webhook_rejects_missing_secret_configuration() -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(telegram_webhook_secret="")

    response = client.post("/api/telegram/webhook", json=_valid_update())

    assert response.status_code == 503
    assert response.json() == {"detail": "Telegram webhook is not configured."}


def test_telegram_webhook_rejects_invalid_secret_header() -> None:
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(FakeEscalationSessionStore())

    response = client.post(
        "/api/telegram/webhook",
        json=_valid_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid Telegram webhook secret."}


def test_telegram_webhook_stores_owner_reply_when_handoff_id_is_found() -> None:
    store = FakeEscalationSessionStore()
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=_valid_update(text="I can discuss availability tomorrow."),
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.appended_messages == [(TEST_HANDOFF_ID, "I can discuss availability tomorrow.")]


def test_telegram_webhook_closes_handoff_with_reply_command() -> None:
    store = FakeEscalationSessionStore()
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=_valid_update(text="/close"),
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.closed_handoff_ids == [TEST_HANDOFF_ID]
    assert store.appended_messages == []


def test_telegram_webhook_closes_handoff_with_inline_command_id() -> None:
    store = FakeEscalationSessionStore()
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=_valid_update(text=f"/close {TEST_HANDOFF_ID}", reply_text=None),
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.closed_handoff_ids == [TEST_HANDOFF_ID]


def test_telegram_webhook_ignores_unknown_command() -> None:
    store = FakeEscalationSessionStore()
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=_valid_update(text="/status"),
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert store.appended_messages == []
    assert store.closed_handoff_ids == []


def test_telegram_webhook_ignores_non_owner_chat() -> None:
    store = FakeEscalationSessionStore()
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(store)

    payload = _valid_update(chat_id=987654321)
    response = client.post(
        "/api/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert store.appended_messages == []


def test_telegram_webhook_ignores_message_without_reply_handoff_id() -> None:
    store = FakeEscalationSessionStore()
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(store)

    payload = _valid_update(reply_text="New handoff request without id")
    response = client.post(
        "/api/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert store.appended_messages == []


def test_telegram_webhook_returns_safe_error_when_store_fails() -> None:
    app.dependency_overrides[get_settings] = lambda: _settings()
    _use_webhook_service(FailingEscalationSessionStore())

    response = client.post(
        "/api/telegram/webhook",
        json=_valid_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": TEST_SECRET},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Telegram reply could not be processed."}


def _valid_update(
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


class FakeEscalationSessionStore:
    def __init__(self) -> None:
        self.appended_messages: list[tuple[str, str]] = []
        self.closed_handoff_ids: list[str] = []

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

    async def close(self, handoff_id: str) -> EscalationSessionRecord | None:
        self.closed_handoff_ids.append(handoff_id)
        return EscalationSessionRecord(
            handoff_id=handoff_id,
            state=ESCALATION_SESSION_STATE_CLOSED,
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-01T02:00:00+00:00",
            transcript=[],
        )


class FailingEscalationSessionStore:
    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("redis failed")

    async def close(self, handoff_id: str) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("redis failed")


def _use_webhook_service(store) -> None:
    app.dependency_overrides[get_telegram_webhook_service] = lambda: TelegramWebhookService(
        owner_chat_id="123456789",
        session_store=store,
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
