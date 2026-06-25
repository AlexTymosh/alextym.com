import pytest

from app.main import app
from app.services.telegram_webhook import (
    CONTACT_QUICK_REPLY,
    READING_QUICK_REPLY,
    STILL_THERE_QUICK_REPLY,
)
from tests.telegram_webhook_helpers import (
    FakeCallbackAcknowledger,
    FakeEscalationSessionStore,
    TEST_HANDOFF_ID,
    VALID_SECRET_HEADERS,
    callback_update,
    client,
    manual_reply_prompt_text,
    quick_reply_confirmation_text,
    use_test_settings,
    use_webhook_service,
)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_telegram_webhook_sends_reading_quick_reply_from_callback() -> None:
    store = FakeEscalationSessionStore()
    callback_acknowledger = FakeCallbackAcknowledger()
    use_test_settings()
    use_webhook_service(store, callback_acknowledger=callback_acknowledger)

    response = client.post(
        "/api/telegram/webhook",
        json=callback_update(f"handoff:reading:{TEST_HANDOFF_ID}"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.appended_messages == [(TEST_HANDOFF_ID, READING_QUICK_REPLY)]
    assert callback_acknowledger.callback_answers == [
        ("callback-1", "Sent to the website chat.", False)
    ]
    assert callback_acknowledger.sent_messages == [
        (quick_reply_confirmation_text(READING_QUICK_REPLY), "HTML", None)
    ]


def test_telegram_webhook_sends_contact_quick_reply_from_callback() -> None:
    store = FakeEscalationSessionStore()
    callback_acknowledger = FakeCallbackAcknowledger()
    use_test_settings()
    use_webhook_service(store, callback_acknowledger=callback_acknowledger)

    response = client.post(
        "/api/telegram/webhook",
        json=callback_update(f"handoff:contact:{TEST_HANDOFF_ID}"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.appended_messages == [(TEST_HANDOFF_ID, CONTACT_QUICK_REPLY)]
    assert callback_acknowledger.callback_answers == [
        ("callback-1", "Sent to the website chat.", False)
    ]
    assert callback_acknowledger.sent_messages == [
        (quick_reply_confirmation_text(CONTACT_QUICK_REPLY), "HTML", None)
    ]


def test_telegram_webhook_sends_still_there_quick_reply_from_callback() -> None:
    store = FakeEscalationSessionStore()
    callback_acknowledger = FakeCallbackAcknowledger()
    use_test_settings()
    use_webhook_service(store, callback_acknowledger=callback_acknowledger)

    response = client.post(
        "/api/telegram/webhook",
        json=callback_update(f"handoff:still:{TEST_HANDOFF_ID}"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.appended_messages == [(TEST_HANDOFF_ID, STILL_THERE_QUICK_REPLY)]
    assert callback_acknowledger.callback_answers == [
        ("callback-1", "Sent to the website chat.", False)
    ]
    assert callback_acknowledger.sent_messages == [
        (quick_reply_confirmation_text(STILL_THERE_QUICK_REPLY), "HTML", None)
    ]


def test_telegram_webhook_reply_callback_opens_force_reply_prompt() -> None:
    store = FakeEscalationSessionStore()
    callback_acknowledger = FakeCallbackAcknowledger()
    use_test_settings()
    use_webhook_service(store, callback_acknowledger=callback_acknowledger)

    response = client.post(
        "/api/telegram/webhook",
        json=callback_update(f"handoff:reply:{TEST_HANDOFF_ID}"),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "handoff_id": TEST_HANDOFF_ID}
    assert store.appended_messages == []
    assert store.closed_handoff_ids == []
    assert callback_acknowledger.callback_answers == [
        ("callback-1", "Manual reply mode opened.", False)
    ]
    assert callback_acknowledger.sent_messages == [
        (
            manual_reply_prompt_text(),
            "HTML",
            {
                "force_reply": True,
                "selective": True,
                "input_field_placeholder": "Type the website chat reply here...",
            },
        )
    ]


def test_telegram_webhook_ignores_non_owner_callback() -> None:
    store = FakeEscalationSessionStore()
    callback_acknowledger = FakeCallbackAcknowledger()
    use_test_settings()
    use_webhook_service(store, callback_acknowledger=callback_acknowledger)

    response = client.post(
        "/api/telegram/webhook",
        json=callback_update(f"handoff:reading:{TEST_HANDOFF_ID}", chat_id=987654321),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert store.appended_messages == []
    assert callback_acknowledger.callback_answers == []
