"""Store integration tests using the existing repository Firestore fixture.

Run against the actual repository, not a substitute domain implementation.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from preferans.online import store
from preferans.online.realtime import RealtimeHub, Ticket
from test_secure_rooms import FakeDB, transactional


@pytest.fixture
def setup_realtime(monkeypatch):
    for key in (
        "PORTFOLIO_LAB_ENABLED",
        "PREFERANS_ROOMS_ENABLED",
        "PREFERANS_REALTIME_ENABLED",
        "PREFERANS_REALTIME_SINGLE_WORKER",
    ):
        monkeypatch.setenv(key, "true")
    runtime = RealtimeHub()
    monkeypatch.setattr(store, "hub", runtime)
    clock = [1_800_000_000_000]
    api = store.FirestoreRooms(
        FakeDB(),
        firestore_module=SimpleNamespace(transactional=transactional),
        now_ms=lambda: clock[0],
    )
    rid = api.create("a", "create-room-01")["room_id"]
    api.join(rid, "b", "join-room-b-01", 0)
    api.join(rid, "c", "join-room-c-01", 1)
    tickets = [
        Ticket(rid, uid, seat, "https://example.test", "credential", clock[0] + 30_000)
        for seat, uid in enumerate("abc")
    ]
    conns = [runtime.connect(ticket, api.view(rid, ticket.uid), clock[0]) for ticket in tickets]
    api.start(rid, "a", "start-room-01", 2, False)
    runtime.synced(rid, clock[0], True, (True, True, True))
    return api, rid, clock, runtime, tickets, conns


def test_commit_publishes_three_distinct_seat_views_and_replay_is_read_only(setup_realtime):
    api, rid, clock, runtime, tickets, conns = setup_realtime
    first = api.view(rid, "a")
    assert first["version"] == 3
    actor = "abc"[first["turn"]]
    token = "one-bid-0001"
    bid = {"bid": {"kind": "regular", "level": 6, "suit": "S"}}
    result = api.command(rid, actor, token, first["version"], "bid", bid)
    before = copy.deepcopy(api.db.docs)
    published = runtime.metrics["published"]
    assert api.command(rid, actor, token, first["version"], "bid", bid) == result
    assert api.db.docs == before
    assert runtime.metrics["published"] == published
    for seat, ticket in enumerate(tickets):
        snapshot = runtime.snapshot(ticket, conns[seat], clock[0])
        assert snapshot == api.view(rid, ticket.uid)
        assert snapshot["my_seat"] == seat
        assert len(snapshot["hand"]) == 10
        assert "discarded" not in snapshot
        assert snapshot["widow"] == []
    assert len({str(runtime.snapshot(t, c, clock[0])["hand"]) for t, c in zip(tickets, conns)}) == 3


def test_fallback_pulse_without_game_version_or_event_write(setup_realtime):
    api, rid, clock, runtime, tickets, conns = setup_realtime
    before = copy.deepcopy(api.db.docs)
    v = api.view(rid, "a")["version"]
    for n in range(1, 5):
        clock[0] += 15_000
        for t, c in zip(tickets, conns):
            runtime.heartbeat(t, c, clock[0])
        pulse = api.command(rid, "a", f"pulse-test-{n:04d}", v, "pulse", {})
        assert pulse["version"] == v
    assert api.db.docs == before


def test_disconnect_pauses_play_and_resume_preserves_game(setup_realtime):
    api, rid, clock, runtime, tickets, conns = setup_realtime
    view = api.view(rid, "a")
    actor = "abc"[view["turn"]]
    runtime.disconnect(tickets[1], conns[1], clock[0])
    api.sync_realtime(rid, "a")
    frozen = api.view(rid, "a")
    assert frozen["controls"]["paused"]
    with pytest.raises(store.StoreError) as denied:
        api.command(rid, actor, "blocked-pass-1", frozen["version"], "pass", {})
    assert denied.value.code == 409
    runtime.connect(tickets[1], api.view(rid, "b"), clock[0])
    api.sync_realtime(rid, "a")
    resumed = api.view(rid, "a")
    assert not resumed["controls"]["paused"]
    assert resumed["game_id"] == view["game_id"]
    assert resumed["hand"] == view["hand"]


def test_failed_commit_does_not_publish(setup_realtime, monkeypatch):
    from test_secure_rooms import FakeTransaction

    api, rid, clock, runtime, tickets, conns = setup_realtime
    view = api.view(rid, "a")
    before = copy.deepcopy(api.db.docs)
    published = runtime.metrics["published"]

    def fail(_self):
        raise RuntimeError("Simulated failed commit")

    monkeypatch.setattr(FakeTransaction, "commit", fail)
    actor = "abc"[view["turn"]]
    with pytest.raises(RuntimeError, match="Simulated failed commit"):
        api.command(rid, actor, "failed-commit-01", view["version"], "pass", {})
    assert api.db.docs == before
    assert runtime.metrics["published"] == published
