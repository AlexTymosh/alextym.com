import pytest

from app.main import app
from tests.telegram_webhook_helpers import (
    FailingEscalationSessionStore,
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


def test_telegram_webhook_returns_safe_error_when_store_fails() -> None:
    use_test_settings()
    use_webhook_service(FailingEscalationSessionStore())

    response = client.post(
        "/api/telegram/webhook",
        json=valid_update(),
        headers=VALID_SECRET_HEADERS,
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Telegram reply could not be processed."}
