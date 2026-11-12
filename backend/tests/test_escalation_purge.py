"""DELETE escalation confirmation and idempotence without real Upstash/Telegram."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.api.escalation import get_escalation_service
from app.main import app
from app.repositories.escalation_session_store import EscalationSessionStoreError
from app.repositories.upstash_escalation_session_store import UpstashRedisEscalationSessionStore
from app.services.escalation import EscalationService

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class TrackingStore:
    def __init__(self, *, fail: bool = False):
        self.keys = {"hnd_test"}
        self.deleted: list[str] = []
        self.fail = fail

    async def delete(self, handoff_id: str) -> None:
        if self.fail:
            raise EscalationSessionStoreError("sensitive internal failure")
        self.deleted.append(handoff_id)
        self.keys.discard(handoff_id)

    async def get(self, handoff_id: str):
        return None  # Streaming is unavailable after deletion.

    async def close(self, handoff_id: str, *, close_message: str | None = None):
        return None


def test_purge_is_idempotent_and_returns_empty_204() -> None:
    store = TrackingStore()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None, session_store=store
    )

    for _ in range(2):
        response = client.delete("/api/escalations/hnd_test")
        assert response.status_code == 204
        assert response.content == b""
    assert store.deleted == ["hnd_test", "hnd_test"]
    assert not store.keys
    assert client.get("/api/escalations/hnd_test/stream").status_code == 404
    assert client.post("/api/escalations/hnd_test/close").status_code == 404


def test_purge_without_redis_configuration_is_503() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None, session_store=None
    )
    response = client.delete("/api/escalations/hnd_test")
    assert response.status_code == 503
    assert response.json() == {"detail": "Escalation session storage is not configured."}


def test_purge_redis_failure_is_safe_502_and_not_204() -> None:
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=None, session_store=TrackingStore(fail=True)
    )
    response = client.delete("/api/escalations/hnd_test")
    assert response.status_code == 502
    assert response.json() == {"detail": "Could not delete this handoff. Please try again later."}
    assert "sensitive" not in response.text


@pytest.mark.parametrize("reply", [None, True, "1", 2, -1])
def test_unconfirmed_redis_del_reply_is_rejected(reply: object) -> None:
    async def scenario():
        store = UpstashRedisEscalationSessionStore(
            rest_url="https://example.invalid/redis", rest_token="test-only"
        )

        async def execute(command: list[object]) -> object:
            assert command == ["DEL", "escalation:session:hnd_test"]
            return reply

        store._execute = execute  # type: ignore[method-assign]
        with pytest.raises(EscalationSessionStoreError, match="confirm"):
            await store.delete("hnd_test")

    asyncio.run(scenario())


@pytest.mark.parametrize("reply", [0, 1])
def test_confirmed_redis_del_reply_is_accepted(reply: int) -> None:
    async def scenario():
        store = UpstashRedisEscalationSessionStore(
            rest_url="https://example.invalid/redis", rest_token="test-only"
        )

        async def execute(command: list[object]) -> int:
            assert command[0] == "DEL"
            return reply

        store._execute = execute  # type: ignore[method-assign]
        assert await store.delete("hnd_test") is None

    asyncio.run(scenario())
