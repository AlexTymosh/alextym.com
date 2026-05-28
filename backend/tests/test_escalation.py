import pytest
from fastapi.testclient import TestClient

from app.api.escalation import get_escalation_service
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.escalation import EscalationMessageRequest, EscalationRequest
from app.services.escalation import EscalationDeliveryError, EscalationService
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    EscalationSessionRecord,
    EscalationSessionStoreError,
)
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
    session_store = FakeEscalationSessionStore()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=session_store,
    )

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
    assert session_store.created_requests == []


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
    assert notifier.sent_handoff_ids == [None]


def test_escalation_creates_redis_ttl_session_when_store_is_configured() -> None:
    notifier = FakeEscalationNotifier()
    session_store = FakeEscalationSessionStore()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=session_store,
        session_ttl_seconds=120,
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

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "handoff_id": "hnd_test",
        "state": ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
        "expires_in_seconds": 120,
    }
    assert len(session_store.created_requests) == 1
    assert session_store.created_ttl_seconds == [120]
    assert notifier.sent_handoff_ids == ["hnd_test"]


def test_escalation_deletes_session_when_telegram_delivery_fails() -> None:
    session_store = FakeEscalationSessionStore()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=FailingEscalationNotifier(),
        session_store=session_store,
        session_ttl_seconds=120,
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
    assert session_store.deleted_handoff_ids == ["hnd_test"]


def test_escalation_returns_safe_error_when_session_store_fails() -> None:
    notifier = FakeEscalationNotifier()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=FailingEscalationSessionStore(),
        session_ttl_seconds=120,
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
    assert notifier.sent_requests == []


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


def test_escalation_message_rejects_blank_content() -> None:
    response = client.post(
        "/api/escalations/hnd_test/messages",
        json={"content": "   ", "company_website": ""},
    )

    assert response.status_code == 422


def test_escalation_message_honeypot_returns_success_without_sending() -> None:
    notifier = FakeEscalationNotifier()
    session_store = FakeEscalationSessionStore()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=session_store,
    )

    response = client.post(
        "/api/escalations/hnd_test/messages",
        json={"content": "Spam", "company_website": "https://spam.example"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert notifier.sent_message_requests == []


def test_escalation_message_sends_valid_message_to_telegram() -> None:
    notifier = FakeEscalationNotifier()
    session_store = FakeEscalationSessionStore(existing_handoff_id="hnd_test")
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=session_store,
    )

    response = client.post(
        "/api/escalations/hnd_test/messages",
        json={"content": "Can we discuss the role details?", "company_website": ""},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(notifier.sent_message_requests) == 1
    assert notifier.sent_message_requests[0].content == "Can we discuss the role details?"
    assert notifier.sent_message_handoff_ids == ["hnd_test"]


def test_escalation_message_returns_404_when_session_is_missing() -> None:
    notifier = FakeEscalationNotifier()
    session_store = FakeEscalationSessionStore(existing_handoff_id=None)
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=session_store,
    )

    response = client.post(
        "/api/escalations/hnd_missing/messages",
        json={"content": "Hello", "company_website": ""},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Escalation session was not found."}
    assert notifier.sent_message_requests == []


def test_escalation_message_returns_503_when_session_store_is_not_configured() -> None:
    notifier = FakeEscalationNotifier()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(notifier=notifier)

    response = client.post(
        "/api/escalations/hnd_test/messages",
        json={"content": "Hello", "company_website": ""},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Escalation messaging is not configured."}
    assert notifier.sent_message_requests == []


def test_escalation_message_returns_safe_error_when_delivery_fails() -> None:
    session_store = FakeEscalationSessionStore(existing_handoff_id="hnd_test")
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=FailingEscalationNotifier(),
        session_store=session_store,
    )

    response = client.post(
        "/api/escalations/hnd_test/messages",
        json={"content": "Hello", "company_website": ""},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not send this message to Alex. Please try again later."
    }


def test_escalation_message_rate_limit_returns_429() -> None:
    notifier = FakeEscalationNotifier()
    session_store = FakeEscalationSessionStore(existing_handoff_id="hnd_test")
    app.dependency_overrides[get_settings] = lambda: _settings(
        escalation_message_daily_limit_per_ip=1
    )
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=session_store,
    )

    payload = {"content": "Hello", "company_website": ""}

    first_response = client.post("/api/escalations/hnd_test/messages", json=payload)
    second_response = client.post("/api/escalations/hnd_test/messages", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.json() == {
        "detail": "Daily request limit reached. Please try again later."
    }


def test_escalation_close_marks_session_closed() -> None:
    session_store = FakeEscalationSessionStore(existing_handoff_id="hnd_test")
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=FakeEscalationNotifier(),
        session_store=session_store,
    )

    response = client.post("/api/escalations/hnd_test/close")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "state": "closed"}
    assert session_store.closed_handoff_ids == ["hnd_test"]


def test_escalation_close_returns_404_when_session_is_missing() -> None:
    session_store = FakeEscalationSessionStore(existing_handoff_id=None)
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=FakeEscalationNotifier(),
        session_store=session_store,
    )

    response = client.post("/api/escalations/hnd_missing/close")

    assert response.status_code == 404
    assert response.json() == {"detail": "Escalation session was not found."}


def test_escalation_close_returns_503_when_session_store_is_not_configured() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=FakeEscalationNotifier(),
    )

    response = client.post("/api/escalations/hnd_test/close")

    assert response.status_code == 503
    assert response.json() == {"detail": "Escalation session storage is not configured."}


def test_escalation_close_returns_safe_error_when_store_fails() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=FakeEscalationNotifier(),
        session_store=FailingEscalationSessionStore(),
    )

    response = client.post("/api/escalations/hnd_test/close")

    assert response.status_code == 502
    assert response.json() == {"detail": "Could not close this handoff. Please try again later."}


def test_escalation_message_returns_404_when_session_is_closed() -> None:
    notifier = FakeEscalationNotifier()
    session_store = FakeEscalationSessionStore(
        existing_handoff_id="hnd_test",
        existing_state=ESCALATION_SESSION_STATE_CLOSED,
    )
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        session_store=session_store,
    )

    response = client.post(
        "/api/escalations/hnd_test/messages",
        json={"content": "Hello", "company_website": ""},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Escalation session was not found."}
    assert notifier.sent_message_requests == []


class FakeEscalationNotifier:
    def __init__(self) -> None:
        self.sent_requests: list[EscalationRequest] = []
        self.sent_handoff_ids: list[str | None] = []
        self.sent_message_requests: list[EscalationMessageRequest] = []
        self.sent_message_handoff_ids: list[str] = []

    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        self.sent_requests.append(escalation_request)
        self.sent_handoff_ids.append(handoff_id)

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        self.sent_message_requests.append(message_request)
        self.sent_message_handoff_ids.append(handoff_id)


class FailingEscalationNotifier:
    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        raise EscalationDeliveryError("provider failed")

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        raise EscalationDeliveryError("provider failed")


class FakeEscalationSessionStore:
    def __init__(
        self,
        *,
        existing_handoff_id: str | None = "hnd_test",
        existing_state: str = ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    ) -> None:
        self.created_requests: list[EscalationRequest] = []
        self.created_ttl_seconds: list[int] = []
        self.deleted_handoff_ids: list[str] = []
        self.closed_handoff_ids: list[str] = []
        self.existing_handoff_id = existing_handoff_id
        self.existing_state = existing_state

    async def create(
        self,
        escalation_request: EscalationRequest,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        self.created_requests.append(escalation_request)
        self.created_ttl_seconds.append(ttl_seconds)
        return _session_record("hnd_test", escalation_request)

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        if self.existing_handoff_id is None or handoff_id != self.existing_handoff_id:
            return None
        return _session_record(handoff_id, state=self.existing_state)

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        return _session_record(handoff_id, state=self.existing_state)

    async def close(self, handoff_id: str) -> EscalationSessionRecord | None:
        if self.existing_handoff_id is None or handoff_id != self.existing_handoff_id:
            return None
        self.closed_handoff_ids.append(handoff_id)
        return _session_record(handoff_id, state=ESCALATION_SESSION_STATE_CLOSED)

    async def delete(self, handoff_id: str) -> None:
        self.deleted_handoff_ids.append(handoff_id)


class FailingEscalationSessionStore:
    async def create(
        self,
        escalation_request: EscalationRequest,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        raise EscalationSessionStoreError("redis failed")

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("redis failed")

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("redis failed")

    async def close(self, handoff_id: str) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("redis failed")

    async def delete(self, handoff_id: str) -> None:
        pass


def _session_record(
    handoff_id: str,
    escalation_request: EscalationRequest | None = None,
    *,
    state: str = ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
) -> EscalationSessionRecord:
    transcript = []
    if escalation_request is not None:
        transcript = [
            {"role": item.role, "content": item.content} for item in escalation_request.transcript
        ]
    return EscalationSessionRecord(
        handoff_id=handoff_id,
        state=state,
        created_at="2026-01-01T00:00:00+00:00",
        expires_at="2099-01-01T00:02:00+00:00",
        transcript=transcript,
    )


def _message(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def _settings(
    *,
    escalation_daily_limit_per_ip: int = 3,
    escalation_message_daily_limit_per_ip: int = 30,
) -> Settings:
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
        escalation_message_daily_limit_per_ip=escalation_message_daily_limit_per_ip,
    )
