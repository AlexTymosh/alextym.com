import pytest
from fastapi.testclient import TestClient

from app.api.contact import get_contact_service
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.contact import ContactRequest
from app.services.contact import ContactDeliveryError, ContactService

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_contact_rejects_invalid_email() -> None:
    response = client.post(
        "/api/contact",
        json={
            "name": "Hiring Manager",
            "email": "not-an-email",
            "message": "Let's talk.",
            "company_website": "",
        },
    )

    assert response.status_code == 422


def test_contact_honeypot_returns_success_without_sending() -> None:
    sender = FakeContactEmailSender()
    app.dependency_overrides[get_contact_service] = lambda: ContactService(sender=sender)

    response = client.post(
        "/api/contact",
        json={
            "name": "Spam Bot",
            "email": "bot@example.com",
            "message": "Spam",
            "company_website": "https://spam.example",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert sender.sent_requests == []


def test_contact_sends_valid_message() -> None:
    sender = FakeContactEmailSender()
    app.dependency_overrides[get_contact_service] = lambda: ContactService(sender=sender)

    response = client.post(
        "/api/contact",
        json={
            "name": "Hiring Manager",
            "email": "hiring@example.com",
            "message": "Let's discuss a backend role.",
            "company_website": "",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(sender.sent_requests) == 1
    assert sender.sent_requests[0].email == "hiring@example.com"


def test_contact_returns_safe_error_when_delivery_fails() -> None:
    app.dependency_overrides[get_contact_service] = lambda: ContactService(
        sender=FailingContactEmailSender()
    )

    response = client.post(
        "/api/contact",
        json={
            "name": "Hiring Manager",
            "email": "hiring@example.com",
            "message": "Let's discuss a backend role.",
            "company_website": "",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Could not send message. Please try again later."}


def test_contact_rate_limit_returns_429() -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(contact_daily_limit_per_ip=1)
    app.dependency_overrides[get_contact_service] = lambda: ContactService(
        sender=FakeContactEmailSender()
    )

    payload = {
        "name": "Hiring Manager",
        "email": "hiring@example.com",
        "message": "Let's discuss a backend role.",
        "company_website": "",
    }

    first_response = client.post("/api/contact", json=payload)
    second_response = client.post("/api/contact", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.json() == {
        "detail": "Daily request limit reached. Please try again later."
    }


class FakeContactEmailSender:
    def __init__(self) -> None:
        self.sent_requests: list[ContactRequest] = []

    async def send(self, contact_request: ContactRequest) -> None:
        self.sent_requests.append(contact_request)


class FailingContactEmailSender:
    async def send(self, contact_request: ContactRequest) -> None:
        raise ContactDeliveryError("provider failed")


def _settings(*, contact_daily_limit_per_ip: int = 5) -> Settings:
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
        contact_daily_limit_per_ip=contact_daily_limit_per_ip,
    )
