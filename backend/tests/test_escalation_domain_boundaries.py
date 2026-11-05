"""Regression contracts for moving escalation state to the pure domain layer.

No external Redis or Telegram connection is used.
"""

from __future__ import annotations

import ast
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain import escalation_session as domain
from app.repositories import escalation_session_store as contract
from app.repositories import upstash_escalation_session_store as redis
from app.services import escalation_session_state as legacy
from app.services import escalation_sessions as facade


PUBLIC_STATE_SYMBOLS = (
    "ESCALATION_SESSION_STATE_WAITING_FOR_ALEX",
    "ESCALATION_SESSION_STATE_CONNECTED",
    "ESCALATION_SESSION_STATE_CLOSED",
    "EscalationSessionRecord",
    "EscalationSessionTransition",
    "build_initial_session_record",
    "build_append_alex_message_transition",
    "build_close_session_transition",
    "remaining_ttl_seconds",
)


def test_legacy_symbols_are_identical_to_domain_implementation() -> None:
    for name in PUBLIC_STATE_SYMBOLS:
        assert getattr(legacy, name) is getattr(domain, name), name

    assert contract.EscalationSessionRecord is domain.EscalationSessionRecord
    assert redis.EscalationSessionRecord is domain.EscalationSessionRecord
    assert facade.EscalationSessionRecord is domain.EscalationSessionRecord
    assert domain.EscalationSessionRecord.__module__ == "app.domain.escalation_session"


def test_redis_wire_payload_and_legacy_role_remain_unchanged() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    initial = domain.build_initial_session_record(
        transcript=[{"role": "user", "content": "Please connect me to the owner."}],
        ttl_seconds=120,
        now=now,
    )
    assert initial.handoff_id.startswith("hnd_")
    assert initial.state == "waiting_for_alex"  # Existing Redis wire state; don't rename.
    assert initial.expires_at == "2026-01-01T00:02:00+00:00"
    transition = domain.build_append_alex_message_transition(initial, "A reply", now=now)
    assert transition.ttl_seconds == 120
    assert transition.record is not None
    record = transition.record
    assert record.state == "connected"
    assert record.messages[0]["role"] == "alex"  # Existing wire role; don't rename.
    expected_keys = {"handoff_id", "state", "created_at", "expires_at", "transcript", "messages"}
    assert set(record.to_dict()) == expected_keys
    assert domain.EscalationSessionRecord.from_dict(record.to_dict()) == record
    assert json.loads(redis._to_json(record)) == record.to_dict()


def test_legacy_payload_coercion_and_closed_expiry_behaviour() -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    record = domain.EscalationSessionRecord.from_dict(
        {
            "handoff_id": "hnd_example",
            "state": domain.ESCALATION_SESSION_STATE_CONNECTED,
            "created_at": "2026-01-31T23:00:00+00:00",
            "expires_at": (now + timedelta(seconds=40)).isoformat(),
            "transcript": [{"role": "user", "content": "Hi"}, None],
            "messages": [{"id": 1, "role": "alex", "content": "Reply", "created_at": "t"}, 8],
        }
    )
    assert record.transcript == [{"role": "user", "content": "Hi"}]
    assert record.messages[0]["id"] == "1"
    closed = domain.build_close_session_transition(record, close_message="Closed", now=now)
    assert closed.record is not None
    assert closed.record.state == "closed"
    assert len(closed.record.messages) == 2
    assert closed.record.messages[-1]["role"] == "alex"
    assert closed.ttl_seconds == 40
    assert (
        domain.build_append_alex_message_transition(closed.record, "Not permitted", now=now).record
        is None
    )
    expired = domain.build_close_session_transition(record, now=now + timedelta(minutes=5))
    assert expired.should_delete and expired.record is None
    assert expired.ttl_seconds is None


def test_upstash_adapter_uses_domain_model_and_preserves_redis_commands() -> None:
    async def scenario() -> None:
        adapter = redis.UpstashRedisEscalationSessionStore(
            rest_url="https://example.invalid/redis", rest_token="test-only"
        )
        stored: dict[str, str] = {}
        commands: list[list[object]] = []

        async def execute(command: list[object]) -> object:
            commands.append(command)
            action = command[0]
            key = str(command[1])
            if action == "SET":
                stored[key] = str(command[2])
                return "OK"
            if action == "GET":
                return stored.get(key)
            if action == "DEL":
                stored.pop(key, None)
                return 1
            raise AssertionError(f"Unexpected command: {command}")

        adapter._execute = execute  # type: ignore[method-assign]
        initial = domain.build_initial_session_record(
            transcript=[{"role": "user", "content": "Request"}], ttl_seconds=120
        )
        assert await adapter.create(initial, ttl_seconds=120) is initial
        assert commands[0][0] == "SET"
        assert commands[0][3:] == ["EX", 120]
        assert commands[0][1] == f"escalation:session:{initial.handoff_id}"
        assert await adapter.get(initial.handoff_id) == initial
        updated = await adapter.append_alex_message(initial.handoff_id, "Reply")
        assert updated is not None and isinstance(updated, domain.EscalationSessionRecord)
        assert updated.state == domain.ESCALATION_SESSION_STATE_CONNECTED
        assert updated.messages[-1]["role"] == "alex"
        closed = await adapter.close(initial.handoff_id, close_message="Finished")
        assert closed is not None and closed.state == domain.ESCALATION_SESSION_STATE_CLOSED
        assert closed.messages[-1]["content"] == "Finished"
        set_commands = [cmd for cmd in commands if cmd[0] == "SET"]
        assert len(set_commands) == 3
        assert all(cmd[3] == "EX" and 0 < int(cmd[4]) <= 120 for cmd in set_commands)
        assert json.loads(stored[f"escalation:session:{initial.handoff_id}"]) == closed.to_dict()
        assert await adapter.get(initial.handoff_id) == closed

    asyncio.run(scenario())


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_domain_module_has_no_dependency_on_application_or_infrastructure() -> None:
    domain_path = Path(domain.__file__).resolve()
    imports = _imported_modules(domain_path)
    assert all(not name.startswith("app.") for name in imports), imports


def test_repository_modules_no_longer_import_application_services() -> None:
    repository_dir = Path(redis.__file__).resolve().parent
    for filename in ("escalation_session_store.py", "upstash_escalation_session_store.py"):
        path = repository_dir / filename
        imports = _imported_modules(path)
        assert not any(
            name == "app.services" or name.startswith("app.services.") for name in imports
        ), (filename, imports)
