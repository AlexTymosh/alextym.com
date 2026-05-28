import pytest
from fastapi.testclient import TestClient

from app.api.escalation import get_escalation_service
from app.main import app
from app.schemas.escalation import EscalationRequest
from app.services.escalation import EscalationService
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_CONNECTED,
    EscalationSessionRecord,
    EscalationSessionStoreError,
)

client = TestClient(app)
TEST_HANDOFF_ID = "hnd_" + "b" * 32


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_escalation_stream_returns_alex_messages() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None,
        session_store=SequenceEscalationSessionStore(
            [
                _session_record(messages=[_alex_message("msg_1", "Hello from Alex")]),
                _session_record(messages=[_alex_message("msg_1", "Hello from Alex")]),
                None,
            ]
        ),
        stream_poll_interval_seconds=0.01,
        stream_heartbeat_interval_seconds=60,
    )

    response = client.get(f"/api/escalations/{TEST_HANDOFF_ID}/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    stream_text = response.text
    assert "event: meta\n" in stream_text
    assert f'"handoff_id":"{TEST_HANDOFF_ID}"' in stream_text
    assert "id: msg_1\n" in stream_text
    assert "event: message\n" in stream_text
    assert '"role":"alex"' in stream_text
    assert '"content":"Hello from Alex"' in stream_text
    assert "event: closed\n" in stream_text


def test_escalation_stream_respects_last_event_id() -> None:
    messages = [
        _alex_message("msg_1", "First message"),
        _alex_message("msg_2", "Second message"),
    ]
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None,
        session_store=SequenceEscalationSessionStore(
            [
                _session_record(messages=messages),
                _session_record(messages=messages),
                _session_record(messages=messages),
                None,
            ]
        ),
        stream_poll_interval_seconds=0.01,
        stream_heartbeat_interval_seconds=60,
    )

    response = client.get(
        f"/api/escalations/{TEST_HANDOFF_ID}/stream",
        headers={"Last-Event-ID": "msg_1"},
    )

    assert response.status_code == 200
    stream_text = response.text
    assert "First message" not in stream_text
    assert "id: msg_2\n" in stream_text
    assert "Second message" in stream_text


def test_escalation_stream_returns_404_for_unknown_handoff_id() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None,
        session_store=SequenceEscalationSessionStore([None]),
    )

    response = client.get(f"/api/escalations/{TEST_HANDOFF_ID}/stream")

    assert response.status_code == 404
    assert response.json() == {"detail": "Escalation session was not found."}


def test_escalation_stream_returns_503_when_session_store_is_not_configured() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None,
        session_store=None,
    )

    response = client.get(f"/api/escalations/{TEST_HANDOFF_ID}/stream")

    assert response.status_code == 503
    assert response.json() == {"detail": "Escalation streaming is not configured."}


def test_escalation_stream_returns_502_when_session_store_fails_before_opening() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None,
        session_store=FailingEscalationSessionStore(),
    )

    response = client.get(f"/api/escalations/{TEST_HANDOFF_ID}/stream")

    assert response.status_code == 502
    assert response.json() == {"detail": "Escalation stream could not be opened."}


class SequenceEscalationSessionStore:
    def __init__(self, records: list[EscalationSessionRecord | None]) -> None:
        self._records = records

    async def create(
        self,
        escalation_request: EscalationRequest,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        raise NotImplementedError

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        if handoff_id != TEST_HANDOFF_ID:
            return None
        if not self._records:
            return None
        return self._records.pop(0)

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        raise NotImplementedError

    async def delete(self, handoff_id: str) -> None:
        pass


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

    async def delete(self, handoff_id: str) -> None:
        pass


def _session_record(*, messages: list[dict[str, str]]) -> EscalationSessionRecord:
    return EscalationSessionRecord(
        handoff_id=TEST_HANDOFF_ID,
        state=ESCALATION_SESSION_STATE_CONNECTED,
        created_at="2026-01-01T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        transcript=[{"role": "user", "content": "Can I speak to Alex?"}],
        messages=messages,
    )


def _alex_message(message_id: str, content: str) -> dict[str, str]:
    return {
        "id": message_id,
        "role": "alex",
        "content": content,
        "created_at": "2026-01-01T00:01:00+00:00",
    }
