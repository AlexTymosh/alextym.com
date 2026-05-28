import pytest
from fastapi.testclient import TestClient

from app.api.escalation import get_escalation_service
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.escalation import EscalationRequest
from app.services.escalation import EscalationDeliveryError, EscalationService
from app.services.rate_limit import get_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    get_rate_limiter().reset()
    yield
    app.dependency_overrides.clear()
    get_rate_limiter().reset()


def test_escalation_requires_consent() -> None:
    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": False,
            "reason": "user_requested_human",
            "transcript": [_message("user", "Can I speak to Alex?")],
            "company_website": "",
        },
    )

    assert response.status_code == 422


def test_escalation_rejects_empty_transcript() -> None:
    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": True,
            "reason": "user_requested_human",
            "transcript": [],
            "company_website": "",
        },
    )

    assert response.status_code == 422


def test_escalation_rejects_oversized_transcript() -> None:
    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": True,
            "reason": "user_requested_human",
            "transcript": [_message("user", "x" * 2000) for _ in range(5)],
            "company_website": "",
        },
    )

    assert response.status_code == 422


def test_escalation_honeypot_returns_success_without_sending() -> None:
    notifier = FakeEscalationNotifier()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(notifier=notifier)

    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": True,
            "reason": "user_requested_human",
            "transcript": [_message("user", "Spam")],
            "company_website": "https://spam.example",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert notifier.sent_requests == []


def test_escalation_sends_valid_transcript() -> None:
    notifier = FakeEscalationNotifier()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(notifier=notifier)

    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": True,
            "reason": "user_requested_human",
            "transcript": [
                _message("user", "When is Alex ready to start work?"),
                _message("assistant", "Would you like me to connect him directly?"),
            ],
            "company_website": "",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(notifier.sent_requests) == 1
    assert notifier.sent_requests[0].reason == "user_requested_human"
    assert notifier.sent_requests[0].transcript[0].role == "user"


def test_escalation_returns_503_when_not_configured() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(notifier=None)

    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": True,
            "reason": "user_requested_human",
            "transcript": [_message("user", "Can I speak to Alex?")],
            "company_website": "",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Escalation is not configured."}


def test_escalation_returns_safe_error_when_delivery_fails() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=FailingEscalationNotifier()
    )

    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": True,
            "reason": "user_requested_human",
            "transcript": [_message("user", "Can I speak to Alex?")],
            "company_website": "",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Could not connect with Alex. Please try again later."}


def test_escalation_rate_limit_returns_429() -> None:
    notifier = FakeEscalationNotifier()
    app.dependency_overrides[get_settings] = lambda: _settings(escalation_daily_limit_per_ip=1)
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(notifier=notifier)

    payload = {
        "consent_accepted": True,
        "reason": "user_requested_human",
        "transcript": [_message("user", "Can I speak to Alex?")],
        "company_website": "",
    }

    first_response = client.post("/api/escalations", json=payload)
    second_response = client.post("/api/escalations", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.json() == {
        "detail": "Daily request limit reached. Please try again later."
    }


class FakeEscalationNotifier:
    def __init__(self) -> None:
        self.sent_requests: list[EscalationRequest] = []

    async def notify(self, escalation_request: EscalationRequest) -> None:
        self.sent_requests.append(escalation_request)


class FailingEscalationNotifier:
    async def notify(self, escalation_request: EscalationRequest) -> None:
        raise EscalationDeliveryError("provider failed")


def _message(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def _settings(*, escalation_daily_limit_per_ip: int = 3) -> Settings:
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
        escalation_daily_limit_per_ip=escalation_daily_limit_per_ip,
    )
