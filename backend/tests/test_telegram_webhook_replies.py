import pytest

from app.main import app
from tests.telegram_webhook_helpers import (
    FakeEscalationSessionStore,
    TEST_HANDOFF_ID,
    VALID_SECRET_HEADERS,
    client,
    use_test_settings,
    use_webhook_service,
    valid_update,
)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_telegram_webhook_stores_owner_reply_when_handoff_id_is_found() -> None:
    store = FakeEscalationSessionStore()
    use_test_settings()
    use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(text="I can discuss availability tomorrow."),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.appended_messages == [(TEST_HANDOFF_ID, "I can discuss availability tomorrow.")]


def test_telegram_webhook_ignores_unknown_command() -> None:
    store = FakeEscalationSessionStore()
    use_test_settings()
    use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(text="/status"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert store.appended_messages == []
    assert store.closed_handoff_ids == []


def test_telegram_webhook_ignores_non_owner_chat() -> None:
    store = FakeEscalationSessionStore()
    use_test_settings()
    use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(chat_id=987654321),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert store.appended_messages == []


def test_telegram_webhook_ignores_message_without_reply_handoff_id() -> None:
    store = FakeEscalationSessionStore()
    use_test_settings()
    use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(reply_text="New handoff request without id"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert store.appended_messages == []
