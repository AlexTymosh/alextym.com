import pytest

from app.main import app
from app.services.telegram_webhook import CLOSE_HANDOFF_REPLY
from tests.telegram_webhook_helpers import (
    FakeCallbackAcknowledger,
    FakeEscalationSessionStore,
    TEST_HANDOFF_ID,
    VALID_SECRET_HEADERS,
    callback_update,
    client,
    close_confirmation_text,
    use_test_settings,
    use_webhook_service,
    valid_update,
)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_telegram_webhook_closes_handoff_with_reply_command() -> None:
    store = FakeEscalationSessionStore()
    use_test_settings()
    use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(text="/close"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.closed_handoff_ids == [(TEST_HANDOFF_ID, None)]
    assert store.appended_messages == []


def test_telegram_webhook_closes_handoff_with_inline_command_id() -> None:
    store = FakeEscalationSessionStore()
    use_test_settings()
    use_webhook_service(store)

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(text=f"/close {TEST_HANDOFF_ID}", reply_text=None),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.closed_handoff_ids == [(TEST_HANDOFF_ID, None)]


def test_telegram_webhook_closes_handoff_from_callback_with_user_message() -> None:
    store = FakeEscalationSessionStore()
    callback_acknowledger = FakeCallbackAcknowledger()
    use_test_settings()
    use_webhook_service(store, callback_acknowledger=callback_acknowledger)

    response = client.post(
        "/api/telegram/webhook",
        json=callback_update(f"handoff:close:{TEST_HANDOFF_ID}"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.closed_handoff_ids == [(TEST_HANDOFF_ID, CLOSE_HANDOFF_REPLY)]
    assert callback_acknowledger.callback_answers == [
        ("callback-1", "Closed and notified the website visitor.", False)
    ]
    assert callback_acknowledger.sent_messages == [(close_confirmation_text(), "HTML", None)]
