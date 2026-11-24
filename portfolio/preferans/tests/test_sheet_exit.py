"""Pure voluntary-exit invariants; no network or Firebase dependency."""

from __future__ import annotations

import copy

import pytest

from preferans.online.sheet_exit import SheetExitError, change, current_offers, finish


def room():
    return {"status": "playing", "seats": ["a", "b", "c"], "game_id": "deal-a", "version": 4}


def test_offer_refusal_and_only_recipient_can_accept():
    r, c = room(), {"timer": {"deadline_ms": 200}, "vote": None}
    e, loser = change(c, r, 0, "sheet_offer", {"target": 1})
    assert e == {"id": 5, "from": 0, "to": 1} and loser is None
    before = copy.deepcopy(c)
    for seat in (0, 2):
        with pytest.raises(SheetExitError):
            change(c, r, seat, "sheet_reply", {"offer_id": 5, "accept": True})
        assert c == before
    event, loser = change(c, r, 1, "sheet_reply", {"offer_id": 5, "accept": False})
    assert event["accepted"] is False and loser is None
    assert current_offers(c, r) == [] and c["timer"] == before["timer"]
    with pytest.raises(SheetExitError):
        change(c, r, 1, "sheet_reply", {"offer_id": 5, "accept": True})


def test_offer_bound_to_deal_and_cannot_be_overwritten():
    r, c = room(), {}
    change(c, r, 0, "sheet_offer", {"target": 1})
    with pytest.raises(SheetExitError):
        change(c, r, 2, "sheet_offer", {"target": 1})
    r.update(game_id="deal-b", version=7)
    assert current_offers(c, r) == []
    with pytest.raises(SheetExitError):
        change(c, r, 1, "sheet_reply", {"offer_id": 5, "accept": True})
    event, loser = change(c, r, 2, "sheet_offer", {"target": 1})
    assert event["id"] == 8 and loser is None
    event, loser = change(c, r, 1, "sheet_reply", {"offer_id": 8, "accept": True})
    assert event["source"] == "accepted" and loser == 1


@pytest.mark.parametrize("seat", [0, 1, 2])
def test_self_exit_is_explicit_and_not_for_someone_else(seat):
    r, c = room(), {}
    for args in ({}, {"confirm": 1}, {"confirm": False}, {"confirm": True, "loser": 2}):
        with pytest.raises(SheetExitError):
            change(c, r, seat, "sheet_discard", args)
    assert change(c, r, seat, "sheet_discard", {"confirm": True}) == (
        {"loser": seat, "source": "voluntary"},
        seat,
    )


@pytest.mark.parametrize("status", ["lobby", "closed"])
def test_inactive_room_rejected(status):
    r = room()
    r["status"] = status
    with pytest.raises(SheetExitError):
        change({}, r, 0, "sheet_discard", {"confirm": True})


def test_finish_clears_pending_clocks_but_preserves_existing_adjustments():
    c = {
        "timer": {"deadline_ms": 1},
        "vote": {},
        "candidate": {},
        "paused_at": 1,
        "pause_reasons": ["break", "shared_overlay"],
        "next_deal": {},
        "sheet_offers": [],
        "presentation": {},
        "adjustments": [{"delta": 2}],
        "policy": {"counter_seconds": 180},
    }
    finish(c)
    assert all(c[key] is None for key in ("timer", "vote", "candidate", "paused_at"))
    assert c["pause_reasons"] == []
    assert all(key not in c for key in ("next_deal", "sheet_offers", "presentation"))
    assert c["adjustments"] == [{"delta": 2}] and c["policy"]["counter_seconds"] == 180
