"""Live signaling tests; relay has no Firestore dependency."""

from __future__ import annotations

import pytest

from preferans.online.live_relay import (
    MAX_QUEUE,
    MAX_WINDOW,
    SIGNAL_TTL_MS,
    LiveError,
    LiveRelay,
    live_enabled,
)

NOW = 1_000_000
ACTIVE = {0: "connection-a", 1: "connection-b", 2: "connection-c"}


def frame(message_type, **args):
    return {"type": message_type, "protocol": 1, **args}


def join(relay, seat, at=NOW):
    relay.receive(seat, ACTIVE[seat], frame("media_join"), at)


def offer(relay, to=1, **overrides):
    data = {
        "to": to,
        "to_session": relay.members[to].session,
        "kind": "offer",
        "data": {"type": "offer", "sdp": "v=0\r\n"},
    }
    return frame("media_signal", **(data | overrides))


@pytest.fixture
def relay():
    result = LiveRelay()
    for seat in ACTIVE:
        join(result, seat)
    return result


def test_gate_requires_explicit_flags(monkeypatch):
    monkeypatch.setenv("PREFERANS_MEDIA_ENABLED", "true")
    monkeypatch.delenv("PREFERANS_LIVE_MEDIA_WS_ENABLED", raising=False)
    assert not live_enabled()
    monkeypatch.setenv("PREFERANS_LIVE_MEDIA_WS_ENABLED", "true")
    assert live_enabled()
    monkeypatch.delenv("PREFERANS_MEDIA_ENABLED")
    assert not live_enabled()


def test_join_defaults_receive_only_and_roster_is_safe(relay):
    roster = relay.snapshot(0, ACTIVE[0])
    assert roster is not None
    assert all(
        p and set(p) == {"session", "audio", "video"} and not p["audio"] and not p["video"]
        for p in roster
    )
    assert "connection" not in str(roster)
    assert relay.snapshot(0, ACTIVE[1]) is None
    relay.receive(0, ACTIVE[0], frame("media_presence", audio=True, video=False), NOW)
    assert relay.snapshot(1, ACTIVE[1])[0]["audio"]


def test_signal_recipient_only_and_no_game_revision(relay):
    relay.receive(0, ACTIVE[0], offer(relay), NOW)
    assert relay.drain(0, ACTIVE[0]) == []
    assert relay.drain(2, ACTIVE[2]) == []
    assert relay.drain(1, ACTIVE[0]) == []
    result = relay.drain(1, ACTIVE[1])
    assert result == [
        {
            "type": "media_signal",
            "from": 0,
            "from_session": relay.members[0].session,
            "to_session": relay.members[1].session,
            "kind": "offer",
            "data": {"type": "offer", "sdp": "v=0\r\n"},
        }
    ]
    assert relay.drain(1, ACTIVE[1]) == []


def test_unjoined_invalid_and_spoofed_sender_denied(relay):
    with pytest.raises(LiveError):
        relay.receive(0, ACTIVE[1], offer(relay), NOW)
    for invalid in [
        offer(relay, to=0),
        offer(relay, to=True),
        offer(relay, **{"from": 2}),
        offer(relay, data={"type": "offer", "sdp": "x" * 12001}),
        offer(relay, kind="ice", data={"candidate": "x", "sdpMLineIndex": True}),
        frame("record_start"),
        frame("media_presence", audio="true", video=False),
    ]:
        with pytest.raises(LiveError):
            relay.receive(0, ACTIVE[0], invalid, NOW)
    assert relay.drain(1, ACTIVE[1]) == []


def test_stale_sender_and_recipient_generations_do_not_deliver(relay):
    message = offer(relay)
    relay.receive(0, ACTIVE[0], message, NOW)
    relay.receive(1, ACTIVE[1], frame("media_leave"), NOW)
    join(relay, 1)
    relay.receive(0, ACTIVE[0], message, NOW)
    assert relay.drain(1, ACTIVE[1]) == []
    relay.receive(0, ACTIVE[0], offer(relay), NOW)
    relay.prune({1: ACTIVE[1], 2: ACTIVE[2]}, NOW + 1)
    assert relay.drain(1, ACTIVE[1]) == []
    assert relay.snapshot(1, ACTIVE[1])[0] is None


def test_new_connection_evicts_old_participant(relay):
    relay.receive(1, ACTIVE[1], offer(relay, to=0), NOW)
    relay.prune({**ACTIVE, 0: "replacement"}, NOW + 1)
    assert relay.snapshot(0, ACTIVE[0]) is None
    assert relay.drain(0, "replacement") == []
    assert relay.snapshot(1, ACTIVE[1])[0] is None


def test_expiry_and_queue_bounds(relay):
    relay.receive(0, ACTIVE[0], offer(relay), NOW)
    relay.prune(ACTIVE, NOW + SIGNAL_TTL_MS)
    assert relay.drain(1, ACTIVE[1]) == []
    for _ in range(MAX_QUEUE):
        relay.receive(0, ACTIVE[0], offer(relay), NOW + SIGNAL_TTL_MS)
    with pytest.raises(LiveError, match="queue full"):
        relay.receive(0, ACTIVE[0], offer(relay), NOW + SIGNAL_TTL_MS)
    assert len(relay.drain(1, ACTIVE[1])) == 8


def test_leave_not_blocked_by_rate_limit(relay):
    for _ in range(MAX_WINDOW - 1):
        relay.receive(0, ACTIVE[0], frame("media_presence", audio=False, video=False), NOW)
    with pytest.raises(LiveError, match="rate limit"):
        relay.receive(0, ACTIVE[0], frame("media_presence", audio=True, video=True), NOW)
    relay.receive(0, ACTIVE[0], frame("media_leave"), NOW)
    assert relay.snapshot(0, ACTIVE[0]) is None
    relay.prune({}, NOW)
    assert relay.rates == {} and relay.members == {}


def test_distinct_relay_instances_cannot_cross_rooms(relay):
    other = LiveRelay()
    join(other, 1)
    relay.receive(0, ACTIVE[0], offer(relay), NOW)
    assert other.drain(1, ACTIVE[1]) == []
