import pytest

from app.main import app
from tests.telegram_webhook_helpers import (
    FakeEscalationSessionStore,
    client,
    use_test_settings,
    use_webhook_service,
    valid_update,
)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_telegram_webhook_rejects_missing_secret_configuration() -> None:
    use_test_settings(telegram_webhook_secret="")

    response = client.post("/api/telegram/webhook", json=valid_update())

    assert response.status_code == 503
    assert response.json() == {"detail": "Telegram webhook is not configured."}


def test_telegram_webhook_rejects_invalid_secret_header() -> None:
    use_test_settings()
    use_webhook_service(FakeEscalationSessionStore())

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid Telegram webhook secret."}
