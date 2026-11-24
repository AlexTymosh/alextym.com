"""Pure realtime and independent-clock tests; no network, Firebase or real users."""

from __future__ import annotations

import pytest

from preferans.online.pause_clock import reasons, synchronize, transition
from preferans.online.realtime import (
    CHECKPOINT_MS,
    MAX_ROOMS,
    MAX_TICKETS,
    TICKET_MS,
    WS_LEASE_MS,
    HubError,
    RealtimeHub,
    enabled,
    origin_allowed,
)

ORIGIN = "https://example.test"
ROOM = "a" * 32
START = 1_800_000_000_000


def view(seat, version=0, room=ROOM, controls=None):
    return {
        "room_id": room,
        "my_seat": seat,
        "version": version,
        "status": "playing",
        "controls": controls or {},
        "hand": [f"only-seat-{seat}"],
    }


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv("PREFERANS_REALTIME_ORIGINS", ORIGIN)
    return RealtimeHub()


def seat(runtime, index, at=START):
    token = runtime.issue(ROOM, f"uid-{index}", index, ORIGIN, "credential", at)
    ticket = runtime.redeem(token, ROOM, ORIGIN, at)
    connection = runtime.connect(ticket, view(index), at)
    return ticket, connection


def test_flag_requires_explicit_single_worker(monkeypatch):
    for key in ("PORTFOLIO_LAB_ENABLED", "PREFERANS_ROOMS_ENABLED", "PREFERANS_REALTIME_ENABLED"):
        monkeypatch.setenv(key, "true")
    monkeypatch.delenv("PREFERANS_REALTIME_SINGLE_WORKER", raising=False)
    assert not enabled()
    monkeypatch.setenv("PREFERANS_REALTIME_SINGLE_WORKER", "true")
    assert enabled()


def test_exact_origin_ticket_scope_expiry_and_replay(runtime):
    assert origin_allowed(ORIGIN)
    for bad in ("", "null", "https://example.test.evil.test", ORIGIN + "/"):
        assert not origin_allowed(bad)
    key = runtime.issue(ROOM, "a", 0, ORIGIN, "credential", START)
    with pytest.raises(HubError):
        runtime.redeem(key, "b" * 32, ORIGIN, START)
    with pytest.raises(HubError):
        runtime.redeem(key, ROOM, ORIGIN, START)
    key = runtime.issue(ROOM, "a", 0, ORIGIN, "credential", START)
    with pytest.raises(HubError):
        runtime.redeem(key, ROOM, ORIGIN, START + TICKET_MS)
    key = runtime.issue(ROOM, "a", 0, ORIGIN, "credential", START)
    ticket = runtime.redeem(key, ROOM, ORIGIN, START)
    assert ticket.uid == "a"
    assert "credential" not in repr(ticket)
    with pytest.raises(HubError):
        runtime.redeem(key, ROOM, ORIGIN, START)


def test_targeted_snapshot_monotonic_and_replaced_connection(runtime):
    pairs = [seat(runtime, i) for i in range(3)]
    runtime.publish(ROOM, {f"uid-{i}": view(i, 8) for i in range(3)}, START)
    runtime.publish(ROOM, {f"uid-{i}": view(i, 7) for i in range(3)}, START)
    for i, (ticket, conn) in enumerate(pairs):
        data = runtime.snapshot(ticket, conn, START)
        assert data["version"] == 8
        assert data["hand"] == [f"only-seat-{i}"]
        assert all(f"only-seat-{j}" not in str(data) for j in range(3) if i != j)
    old, old_conn = pairs[0]
    new, new_conn = seat(runtime, 0, START + 100)
    assert not runtime.current(old, old_conn, START + 100)
    runtime.disconnect(old, old_conn, START + 101)
    assert runtime.current(new, new_conn, START + 101)
    with pytest.raises(HubError):
        runtime.snapshot(old, old_conn, START + 101)


def test_six_hour_heartbeat_simulation_has_no_version_or_storage_operations(runtime):
    pairs = [seat(runtime, i) for i in range(3)]
    assert runtime.due(ROOM, START)
    assert not runtime.due(ROOM, START)
    runtime.synced(ROOM, START, True, (True, True, True))
    for at in range(START + 15_000, START + 6 * 3600_000 + 1, 15_000):
        for ticket, conn in pairs:
            runtime.heartbeat(ticket, conn, at)
        assert not runtime.due(ROOM, at)
    assert runtime.metrics["heartbeats"] == 4320
    assert runtime.metrics["sync_reads"] == runtime.metrics["sync_writes"] == 0
    assert runtime.rooms[ROOM].revision == 0
    assert runtime.statuses(ROOM, at) == ["online"] * 3


def test_presence_disconnect_stale_reconnect_and_fallback(runtime):
    a, ca = seat(runtime, 0)
    b, cb = seat(runtime, 1)
    seat(runtime, 2)
    runtime.disconnect(b, cb, START + 10_000)
    assert runtime.statuses(ROOM, START + 10_001) == ["online", "reconnecting", "online"]
    assert runtime.presence(ROOM, ["uid-0", "uid-1", "uid-2"], START + 10_001)[1] is None
    gen, pending = runtime.generation(ROOM)
    assert pending
    runtime.fallback(ROOM, "uid-1", view(1), START + 10_002)
    assert runtime.statuses(ROOM, START + 10_002) == ["online"] * 3
    # A quick reconnect cannot erase a loss before reconciliation.
    assert runtime.generation(ROOM)[1]
    runtime.handled(ROOM, gen)
    assert runtime.generation(ROOM)[1]
    assert runtime.statuses(ROOM, START + WS_LEASE_MS + 1)[0] == "reconnecting"
    with pytest.raises(HubError):
        runtime.heartbeat(a, ca, START + WS_LEASE_MS + 1)
    assert runtime.statuses(ROOM, START + WS_LEASE_MS + 60_001)[0] == "offline"


def test_checkpoint_and_timer_due_are_coalesced(runtime):
    pairs = [seat(runtime, i) for i in range(3)]
    runtime.publish(
        ROOM,
        {
            f"uid-{i}": view(i, 1, controls={"counter": {"deadline_ms": START + 180_000}})
            for i in range(3)
        },
        START,
    )
    runtime.synced(ROOM, START, True, (True, True, True))
    for at in range(START + 15_000, START + CHECKPOINT_MS + 1, 15_000):
        for ticket, conn in pairs:
            runtime.heartbeat(ticket, conn, at)
    assert runtime.due(ROOM, at)
    assert not runtime.due(ROOM, at)
    runtime.synced(ROOM, at, True, (True, True, True))
    assert not runtime.due(ROOM, at)


def test_ticket_and_room_caps(runtime):
    for i in range(MAX_TICKETS):
        runtime.issue(ROOM, str(i), 0, ORIGIN, "credential", START)
    with pytest.raises(HubError):
        runtime.issue(ROOM, "another", 0, ORIGIN, "credential", START)
    assert len(runtime.tickets) == MAX_TICKETS
    for i in range(MAX_ROOMS):
        rid = f"{i:032x}"
        runtime.fallback(rid, "uid", view(0, room=rid), START)
    with pytest.raises(HubError):
        runtime.fallback("z" * 32, "uid", view(0, room="z" * 32), START)


def clock():
    return {
        "timer": {"deadline_ms": START + 180_000, "period_ms": 180_000},
        "vote": None,
        "paused_at": None,
        "rt_epoch": "old",
        "rt_checkpoint_ms": START + 120_000,
    }


def test_independent_pause_preserves_remainder_and_vote_clock():
    c = clock()
    assert transition(c, {"shared_overlay"}, START + 120_000)
    assert c["timer"]["remaining_ms"] == 60_000
    transition(c, {"shared_overlay", "connection_lost"}, START + 300_000)
    transition(c, {"connection_lost"}, START + 600_000)
    assert c["timer"]["deadline_ms"] is None
    assert c["timer"]["remaining_ms"] == 60_000
    transition(c, set(), START + 900_000)
    assert c["timer"]["deadline_ms"] == START + 960_000
    c = clock()
    c["timer"] = {"deadline_ms": None, "remaining_ms": 60_000}
    c["vote"] = {"deadline_ms": START + 170_000}
    transition(c, {"break"}, START + 120_000)
    transition(c, set(), START + 600_000)
    assert c["timer"]["deadline_ms"] is None
    assert c["vote"]["deadline_ms"] == START + 650_000


def test_restart_conservative_freeze_never_charges_unknown_downtime():
    c = clock()
    at = START + 3_600_000
    events = synchronize(c, [None, None, None], "new", at)
    assert events[0]["action"] == "room_paused"
    assert c["timer"]["remaining_ms"] == 60_000
    assert reasons(c) == {"connection_lost"}
    events = synchronize(c, [at + 10] * 3, "new", at + 10)
    assert events[0]["action"] == "room_resumed"
    assert c["timer"]["deadline_ms"] == at + 60_010
    assert reasons(c) == set()


def test_quick_reconnect_with_other_pause_never_resumes_counter():
    c = clock()
    transition(c, {"break"}, START + 120_000)
    synchronize(c, [START + 900_000] * 3, "old", START + 900_000, interrupted=True)
    assert reasons(c) == {"break"}
    assert c["timer"]["remaining_ms"] == 60_000
    assert c["timer"]["deadline_ms"] is None
