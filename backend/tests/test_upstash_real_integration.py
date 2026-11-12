"""Opt-in integration contracts for an isolated, non-production Upstash Redis.

These tests execute the actual REST transport and Lua script; unit tests use a
simulator and cannot establish live EVAL support. The suite never uses the
application's production UPSTASH_REDIS_REST_URL / TOKEN environment variables.

Required explicit opt-in:
    RUN_UPSTASH_INTEGRATION=1
    UPSTASH_TEST_ACK_NONPRODUCTION=YES
    UPSTASH_TEST_REST_URL=https://<test-instance>.upstash.io
    UPSTASH_TEST_REST_TOKEN=<test-only-token>

Only unique, short-lived test keys are touched. Never use production credentials.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import AsyncIterator
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from app.domain.escalation_session import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_CONNECTED,
    EscalationSessionRecord,
    build_initial_session_record,
)
from app.repositories.upstash_escalation_session_store import (
    ATOMIC_CAS_SCRIPT,
    ESCALATION_SESSION_KEY_PREFIX,
    UpstashRedisEscalationSessionStore,
)

# A leaked key must also disappear without the test runner or cleanup working.
TEST_SESSION_TTL_SECONDS = 90


@pytest.fixture(scope="module")
def upstash_test_store() -> UpstashRedisEscalationSessionStore:
    if os.environ.get("RUN_UPSTASH_INTEGRATION") != "1":
        pytest.skip("Live Upstash checks are opt-in; set RUN_UPSTASH_INTEGRATION=1")

    if os.environ.get("UPSTASH_TEST_ACK_NONPRODUCTION") != "YES":
        pytest.fail("Explicitly confirm a non-production Redis database before running")

    url = os.environ.get("UPSTASH_TEST_REST_URL", "")
    token = os.environ.get("UPSTASH_TEST_REST_TOKEN", "")
    if not url or not token:
        pytest.fail("UPSTASH_TEST_REST_URL and UPSTASH_TEST_REST_TOKEN are required")

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".upstash.io")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        pytest.fail("Test Redis URL must be a plain HTTPS *.upstash.io REST endpoint")

    return UpstashRedisEscalationSessionStore(rest_url=url, rest_token=token)


@asynccontextmanager
async def isolated_session(
    store: UpstashRedisEscalationSessionStore,
    *,
    ttl_seconds: int = TEST_SESSION_TTL_SECONDS,
) -> AsyncIterator[EscalationSessionRecord]:
    record = replace(
        build_initial_session_record(
            transcript=[{"role": "user", "content": "Integration test only"}],
            ttl_seconds=ttl_seconds,
        ),
        handoff_id=f"hnd_integration_{uuid4().hex}",
    )
    try:
        yield record
    finally:
        # Idempotent DEL also removes keys if an assertion failed partway through.
        await store.delete(record.handoff_id)


def test_real_upstash_eval_cas_set_and_ttl(
    upstash_test_store: UpstashRedisEscalationSessionStore,
) -> None:
    async def scenario() -> None:
        store = upstash_test_store
        async with isolated_session(store) as record:
            key = f"{ESCALATION_SESSION_KEY_PREFIX}{record.handoff_id}"
            await store.create(record, ttl_seconds=TEST_SESSION_TTL_SECONDS)
            before = await store._execute(["GET", key])
            assert isinstance(before, str)
            assert set(json.loads(before)) == {
                "handoff_id",
                "state",
                "created_at",
                "expires_at",
                "transcript",
                "messages",
            }
            assert (
                await store._execute(["EVAL", ATOMIC_CAS_SCRIPT, "1", key, "stale", "delete"]) == 0
            )

            updated = await store.append_alex_message(record.handoff_id, "One reply")
            assert updated is not None
            assert updated.state == ESCALATION_SESSION_STATE_CONNECTED
            assert [message["content"] for message in updated.messages] == ["One reply"]
            assert await store.get(record.handoff_id) == updated
            assert 0 < await store._execute(["TTL", key]) <= TEST_SESSION_TTL_SECONDS

            # A snapshot read before the append cannot replace its result.
            assert (
                await store._execute(
                    ["EVAL", ATOMIC_CAS_SCRIPT, "1", key, before, "set", before, 60]
                )
                == 0
            )
            assert await store.get(record.handoff_id) == updated

            closed = await store.close(record.handoff_id, close_message="Closed")
            assert closed is not None
            assert closed.state == ESCALATION_SESSION_STATE_CLOSED
            assert [message["content"] for message in closed.messages] == [
                "One reply",
                "Closed",
            ]
            assert await store.close(record.handoff_id) == closed
            assert await store.append_alex_message(record.handoff_id, "Too late") is None
            assert 0 < await store._execute(["TTL", key]) <= TEST_SESSION_TTL_SECONDS

    asyncio.run(scenario())


def test_real_upstash_eval_delete_and_no_resurrection(
    upstash_test_store: UpstashRedisEscalationSessionStore,
) -> None:
    async def scenario() -> None:
        store = upstash_test_store
        async with isolated_session(store) as record:
            key = f"{ESCALATION_SESSION_KEY_PREFIX}{record.handoff_id}"
            await store.create(record, ttl_seconds=TEST_SESSION_TTL_SECONDS)
            snapshot = await store._execute(["GET", key])
            assert isinstance(snapshot, str)

            # Real Lua CAS delete succeeds for exactly the observed snapshot.
            assert (
                await store._execute(["EVAL", ATOMIC_CAS_SCRIPT, "1", key, snapshot, "delete"]) == 1
            )
            assert await store.get(record.handoff_id) is None

            # No stale writer may re-create an already deleted session.
            assert (
                await store._execute(
                    ["EVAL", ATOMIC_CAS_SCRIPT, "1", key, snapshot, "set", snapshot, 60]
                )
                == 0
            )
            assert await store.append_alex_message(record.handoff_id, "Too late") is None
            assert await store.close(record.handoff_id) is None
            assert await store._execute(["EXISTS", key]) == 0

    asyncio.run(scenario())


def test_real_upstash_concurrent_append_and_close(
    upstash_test_store: UpstashRedisEscalationSessionStore,
) -> None:
    async def scenario() -> None:
        store = upstash_test_store
        async with isolated_session(store) as record:
            await store.create(record, ttl_seconds=TEST_SESSION_TTL_SECONDS)
            contents = ["Concurrent A", "Concurrent B", "Concurrent C"]
            results = await asyncio.gather(
                *(store.append_alex_message(record.handoff_id, value) for value in contents)
            )
            assert all(result is not None for result in results)
            before_close = await store.get(record.handoff_id)
            assert before_close is not None
            assert len(before_close.messages) == len(contents)
            assert {item["content"] for item in before_close.messages} == set(contents)
            assert len({item["id"] for item in before_close.messages}) == len(contents)

            late_append, closed = await asyncio.gather(
                store.append_alex_message(record.handoff_id, "At close"),
                store.close(record.handoff_id, close_message="Closing"),
            )
            current = await store.get(record.handoff_id)
            assert closed is not None and current is not None
            assert current.state == ESCALATION_SESSION_STATE_CLOSED
            assert current.messages[-1]["content"] == "Closing"
            current_contents = [item["content"] for item in current.messages]
            assert set(contents).issubset(current_contents)
            if late_append is not None:
                assert "At close" in current_contents
            assert await store.append_alex_message(record.handoff_id, "After close") is None

    asyncio.run(scenario())


def test_real_upstash_del_zero_one_and_expiry(
    upstash_test_store: UpstashRedisEscalationSessionStore,
) -> None:
    async def scenario() -> None:
        store = upstash_test_store
        async with isolated_session(store, ttl_seconds=3) as record:
            key = f"{ESCALATION_SESSION_KEY_PREFIX}{record.handoff_id}"
            await store.create(record, ttl_seconds=3)
            assert await store._execute(["EXISTS", key]) == 1
            await asyncio.sleep(3.2)
            assert await store._execute(["EXISTS", key]) == 0
            assert await store.get(record.handoff_id) is None
            assert await store._execute(["DEL", key]) == 0

        async with isolated_session(store) as record:
            key = f"{ESCALATION_SESSION_KEY_PREFIX}{record.handoff_id}"
            await store.create(record, ttl_seconds=TEST_SESSION_TTL_SECONDS)
            assert await store._execute(["DEL", key]) == 1
            assert await store._execute(["DEL", key]) == 0
            await store.delete(record.handoff_id)
            await store.delete(record.handoff_id)
            assert await store.get(record.handoff_id) is None

    asyncio.run(scenario())
