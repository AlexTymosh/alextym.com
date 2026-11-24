"""Pure consent and atomic seat-binding regression tests."""

import copy

import pytest

from preferans.online.realtime import HubError, RealtimeHub, Ticket
from preferans.online.seat_swap import SeatSwapError, change, projection


def lobby():
    return {
        "status": "lobby",
        "seats": ["a", "b", "c"],
        "game_id": None,
        "version": 3,
        "lobby_setup": {"dealer": 0, "ready": [True] * 3},
    }, {"presence": [1, 2, 3]}


def offer(room, controls):
    return change(room, controls, 0, "seat_swap_offer", {"to": 1})


def vote(room, controls, seat, approve=True, id_=4):
    return change(room, controls, seat, "seat_swap_vote", {"id": id_, "approve": approve})


def test_unanimous_swap_preserves_dealer_identity():
    room, control = lobby()
    assert offer(room, control)[1] is False
    assert projection(room) == {"id": 4, "from": 0, "to": 1, "votes": [True, False, False]}
    assert vote(room, control, 1)[1] is False
    assert room["seats"] == ["a", "b", "c"]
    assert vote(room, control, 2)[1] is True
    assert room["seats"] == ["b", "a", "c"]
    assert room["lobby_setup"] == {"dealer": 1, "ready": [False] * 3}
    assert room["seat_revision"] == 1
    assert control["presence"] == [None] * 3
    assert projection(room) is None


@pytest.mark.parametrize("seat", [0, 1, 2])
def test_any_refusal_leaves_configuration_unchanged(seat):
    room, control = lobby()
    before = copy.deepcopy(room)
    offer(room, control)
    assert vote(room, control, seat, False)[1] is False
    assert room == before
    assert control["presence"] == [1, 2, 3]


@pytest.mark.parametrize("to", [0, True, -1, 3, "1", None])
def test_rejects_bad_target(to):
    room, control = lobby()
    before = copy.deepcopy(room)
    with pytest.raises(SeatSwapError):
        change(room, control, 0, "seat_swap_offer", {"to": to})
    assert room == before


def test_rejects_duplicate_vote_stale_offer_and_second_offer():
    room, control = lobby()
    offer(room, control)
    for operation in (
        lambda: offer(room, control),
        lambda: vote(room, control, 0),
        lambda: vote(room, control, 1, id_=3),
    ):
        with pytest.raises(SeatSwapError):
            operation()
    assert projection(room)["votes"] == [True, False, False]


@pytest.mark.parametrize("status", ["playing", "between", "closed", "awaiting_settlement"])
def test_no_seat_changes_after_start(status):
    room, control = lobby()
    room["status"] = status
    with pytest.raises(SeatSwapError):
        offer(room, control)


def test_rejects_partial_and_legacy_lobby():
    room, control = lobby()
    room["seats"][2] = None
    with pytest.raises(SeatSwapError):
        offer(room, control)
    room["seats"][2] = "c"
    del room["lobby_setup"]
    with pytest.raises(SeatSwapError):
        offer(room, control)


def test_revokes_old_tickets_connections_and_media_only_in_changed_room(monkeypatch):
    runtime = RealtimeHub()
    origin = "https://example.test"
    monkeypatch.setenv("PREFERANS_REALTIME_ORIGINS", origin)
    rid, other = "a" * 32, "b" * 32
    at = 100_000
    pairs = []
    for room in (rid, other):
        for seat in range(3):
            ticket = Ticket(room, f"user-{seat}", seat, origin, "credential", at + 30_000)
            conn = runtime.connect(ticket, {"room_id": room, "my_seat": seat, "version": 2}, at)
            pairs.append((ticket, conn))
    token = runtime.issue(rid, "user-0", 0, origin, "credential", at)
    other_token = runtime.issue(other, "user-0", 0, origin, "credential", at)
    old = runtime.rooms[rid].live_media
    old.receive(0, pairs[0][1], {"type": "media_join", "protocol": 1}, at)
    assert old.members
    runtime.invalidate_seats(rid, at + 1)
    for ticket, conn in pairs[:3]:
        assert not runtime.current(ticket, conn, at + 1)
        with pytest.raises(HubError):
            runtime.snapshot(ticket, conn, at + 1)
    for ticket, conn in pairs[3:]:
        assert runtime.current(ticket, conn, at + 1)
    with pytest.raises(HubError):
        runtime.redeem(token, rid, origin, at + 1)
    assert runtime.redeem(other_token, other, origin, at + 1).room == other
    assert not runtime.rooms[rid].live_media.members
    assert not runtime.rooms[rid].views
    assert not runtime.rooms[rid].leases
