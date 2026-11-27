"""Regression coverage for single-shot counters and durable decision outcomes."""

import pytest

from preferans.domain.auction import RuleViolation
from preferans.domain.claims import offer_claim
from preferans.online.codec import decode, encode
from preferans.online.store import StoreError
from test_game_controls import pulse_all, service
from test_pr24_claims_scoring import passout


def test_display_order_is_validated_without_reordering_private_hand():
    state = passout()
    cards = tuple(reversed(state.hands[0]))
    offered = offer_claim(state, 0, cards)
    assert offered.claim.display_order == cards
    assert offered.hands == state.hands
    assert decode(encode(offered)) == offered
    with pytest.raises(RuleViolation):
        offer_claim(state, 0, cards[:-1])
    with pytest.raises(RuleViolation):
        offer_claim(state, 0, (cards[0],) * len(cards))


def test_start_counter_revokes_previous_undo(monkeypatch):
    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    api, rid, clock = service()
    current = api.view(rid, "a")
    seat = current["turn"]
    player = "abc"[seat]
    api.command(
        rid,
        player,
        "pr36-bid-0001",
        current["version"],
        "bid",
        {"bid": {"kind": "regular", "level": 6, "suit": "S"}},
    )
    pulse_all(api, rid, clock)
    seen = api.view(rid, player)
    assert seen["controls"]["can_request_undo"]
    api.command(rid, player, "pr36-start-01", seen["version"], "counter_start", {})
    seen = api.view(rid, player)
    assert not seen["controls"]["can_request_undo"]
    with pytest.raises(StoreError) as exc:
        api.command(
            rid,
            player,
            "pr36-undo-denied",
            seen["version"],
            "undo_request",
            {"reason": "Wrong bid"},
        )
    assert exc.value.code == 409
