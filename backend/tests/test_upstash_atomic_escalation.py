"""Deterministic Redis CAS tests with forced concurrent readers; no real Redis or secrets."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.escalation_session import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_CONNECTED,
    EscalationSessionRecord,
    build_initial_session_record,
)
from app.repositories.escalation_session_store import EscalationSessionStoreError
from app.repositories.upstash_escalation_session_store import (
    ATOMIC_CAS_SCRIPT,
    MAX_CAS_ATTEMPTS,
    UpstashRedisEscalationSessionStore,
)


class AtomicRedisSimulator:
    """Imitates the GET/SET/DEL/EVAL command semantics, not Lua implementation.

    A barrier may release two GET requests with the SAME snapshot to reproduce
    the lost-update race that the old Python read/modify/write had.
    """

    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.commands: list[list[object]] = []
        self.barrier_enabled = False
        self._reads = 0
        self._both_read = asyncio.Event()
        self.force_conflict = False
        self.force_bad_reply = False

    async def execute(self, command: list[object]) -> object:
        self.commands.append(command)
        action = command[0]
        if action == "SET":
            key = str(command[1])
            self.storage[key] = str(command[2])
            assert command[3] == "EX"
            self.ttls[key] = int(command[4])
            return "OK"
        if action == "GET":
            key = str(command[1])
            snapshot = self.storage.get(key)
            if self.barrier_enabled and self._reads < 2:
                self._reads += 1
                if self._reads == 2:
                    self._both_read.set()
                await self._both_read.wait()
            return snapshot
        if action == "DEL":
            self.storage.pop(str(command[1]), None)
            self.ttls.pop(str(command[1]), None)
            return 1
        if action == "EVAL":
            assert command[1] == ATOMIC_CAS_SCRIPT
            assert command[2] == "1"
            key, expected, mode = str(command[3]), str(command[4]), str(command[5])
            if self.force_bad_reply:
                return "not-an-integer"
            if self.force_conflict or self.storage.get(key) != expected:
                return 0
            if mode == "delete":
                self.storage.pop(key, None)
                self.ttls.pop(key, None)
            elif mode == "set":
                assert len(command) == 8
                ttl = int(command[7])
                assert ttl > 0
                self.storage[key] = str(command[6])
                self.ttls[key] = ttl
            else:
                raise AssertionError(f"Unexpected CAS mode: {mode}")
            return 1
        raise AssertionError(f"Unexpected command: {command}")


def _adapter(sim: AtomicRedisSimulator) -> UpstashRedisEscalationSessionStore:
    adapter = UpstashRedisEscalationSessionStore(
        rest_url="https://example.invalid/redis", rest_token="test-only"
    )
    adapter._execute = sim.execute  # type: ignore[method-assign]
    return adapter


def _record(ttl_seconds: int = 120) -> EscalationSessionRecord:
    return build_initial_session_record(
        transcript=[{"role": "user", "content": "Request the owner"}],
        ttl_seconds=ttl_seconds,
    )


def test_simultaneous_appends_preserve_both_messages_without_lost_update() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        await adapter.create(initial, ttl_seconds=120)
        redis.barrier_enabled = True
        first, second = await asyncio.gather(
            adapter.append_alex_message(initial.handoff_id, "Message A"),
            adapter.append_alex_message(initial.handoff_id, "Message B"),
        )
        final = await adapter.get(initial.handoff_id)
        assert first is not None and second is not None and final is not None
        assert final.state == ESCALATION_SESSION_STATE_CONNECTED
        assert {message["content"] for message in final.messages} == {"Message A", "Message B"}
        assert len({message["id"] for message in final.messages}) == 2
        assert sum(cmd[0] == "EVAL" for cmd in redis.commands) == 3
        assert all(ttl <= 120 for ttl in redis.ttls.values())

    asyncio.run(scenario())


def test_concurrent_close_and_append_never_reopens_closed_session() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        await adapter.create(initial, ttl_seconds=120)
        redis.barrier_enabled = True
        appended, closed = await asyncio.gather(
            adapter.append_alex_message(initial.handoff_id, "Before close"),
            adapter.close(initial.handoff_id, close_message="Conversation closed"),
        )
        final = await adapter.get(initial.handoff_id)
        assert final is not None and closed is not None
        assert final.state == ESCALATION_SESSION_STATE_CLOSED
        assert closed.state == ESCALATION_SESSION_STATE_CLOSED
        contents = [message["content"] for message in final.messages]
        if appended is None:
            assert contents == ["Conversation closed"]
        else:
            assert contents == ["Before close", "Conversation closed"]
        assert await adapter.append_alex_message(initial.handoff_id, "Too late") is None
        assert await adapter.get(initial.handoff_id) == final

    asyncio.run(scenario())


def test_close_is_idempotent_and_does_not_overwrite_closed_json() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        await adapter.create(initial, ttl_seconds=120)
        closed = await adapter.close(initial.handoff_id)
        assert closed is not None and closed.state == ESCALATION_SESSION_STATE_CLOSED
        eval_count = sum(cmd[0] == "EVAL" for cmd in redis.commands)
        repeated = await adapter.close(initial.handoff_id)
        assert repeated == closed
        assert sum(cmd[0] == "EVAL" for cmd in redis.commands) == eval_count

    asyncio.run(scenario())


def test_expired_snapshot_is_deleted_only_if_still_current() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        expired = replace(
            initial,
            expires_at=(datetime.now(UTC) - timedelta(seconds=10)).isoformat(),
        )
        await adapter.create(expired, ttl_seconds=120)
        assert await adapter.append_alex_message(initial.handoff_id, "Too late") is None
        assert await adapter.get(initial.handoff_id) is None
        assert any(cmd[0] == "EVAL" and cmd[5] == "delete" for cmd in redis.commands)

    asyncio.run(scenario())


def test_cas_conflict_never_overwrites_and_is_bounded() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        await adapter.create(initial, ttl_seconds=120)
        redis.force_conflict = True
        with pytest.raises(EscalationSessionStoreError, match="concurrent"):
            await adapter.append_alex_message(initial.handoff_id, "Message")
        assert await adapter.get(initial.handoff_id) == initial
        assert sum(cmd[0] == "EVAL" for cmd in redis.commands) == MAX_CAS_ATTEMPTS

    asyncio.run(scenario())


def test_unexpected_redis_cas_result_fails_closed() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        await adapter.create(initial, ttl_seconds=120)
        redis.force_bad_reply = True
        with pytest.raises(EscalationSessionStoreError, match="CAS"):
            await adapter.close(initial.handoff_id)
        assert await adapter.get(initial.handoff_id) == initial

    asyncio.run(scenario())


def test_deleted_or_missing_session_is_never_resurrected() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        assert await adapter.append_alex_message(initial.handoff_id, "No session") is None
        assert await adapter.close(initial.handoff_id) is None
        await adapter.create(initial, ttl_seconds=120)
        await adapter.delete(initial.handoff_id)
        assert await adapter.append_alex_message(initial.handoff_id, "Too late") is None
        assert not any(cmd[0] == "EVAL" for cmd in redis.commands)

    asyncio.run(scenario())


def test_atomic_set_keeps_existing_wire_contract_and_ttl() -> None:
    async def scenario() -> None:
        redis = AtomicRedisSimulator()
        adapter = _adapter(redis)
        initial = _record()
        await adapter.create(initial, ttl_seconds=120)
        updated = await adapter.append_alex_message(initial.handoff_id, "Reply")
        assert updated is not None
        key = f"escalation:session:{initial.handoff_id}"
        value = json.loads(redis.storage[key])
        assert set(value) == {
            "handoff_id",
            "state",
            "created_at",
            "expires_at",
            "transcript",
            "messages",
        }
        assert value["messages"][0]["role"] == "alex"
        assert 0 < redis.ttls[key] <= 120

    asyncio.run(scenario())
