"""Declaration-only concession and between-deal dealer projection."""

from dataclasses import replace

import pytest

from preferans.domain import Bid, DefenseDecision, EndReason, FULL_DECK, Phase, RuleViolation, Suit
from preferans.domain import deal, start_game
from preferans.online.commands import apply_command, redacted_action
from preferans.online.views import seat_view


BID = {"kind": "regular", "level": 7, "suit": "H"}


def declaration():
    return replace(
        start_game(deal(FULL_DECK, 2)),
        phase=Phase.DECLARE,
        declarer=0,
        turn=0,
        winning_bid=Bid.regular(7, Suit.HEARTS),
    )


def test_without_three_is_one_authoritative_declaration():
    state = declaration()
    result = apply_command(state, 0, "without_three", {"bid": BID})
    assert result.phase == Phase.FINISHED
    assert result.end_reason == EndReason.WITHOUT_THREE
    assert result.contract == Bid.regular(7, Suit.HEARTS)
    assert result.turn is None and not any(result.defense)
    assert redacted_action("without_three", {"bid": BID}) == {"bid": BID}
    assert state.phase == Phase.DECLARE


@pytest.mark.parametrize("phase", [Phase.DEFENSE_FIRST, Phase.DEFENSE_SECOND, Phase.PLAY])
def test_without_three_cannot_follow_contract_or_defense(phase):
    state = replace(
        declaration(),
        phase=phase,
        contract=Bid.regular(7, Suit.HEARTS),
        defense=(None, DefenseDecision.VIST, None),
    )
    with pytest.raises(RuleViolation):
        apply_command(state, 0, "without_three", {"bid": BID})


def test_concession_rejects_other_actor_missing_bid_and_lower_bid():
    for actor, args in [(1, {"bid": BID}), (0, {}), (0, {"bid": {**BID, "level": 6}})]:
        with pytest.raises(RuleViolation):
            apply_command(declaration(), actor, "without_three", args)


def test_between_deal_projection_preserves_dealer_without_game():
    room = {
        "id": "a" * 32,
        "seats": ["a", "b", "c"],
        "status": "between",
        "admin_uid": "a",
        "dealer": 0,
        "game_id": "old",
    }
    view = seat_view(room, None, None, "b", 7)
    assert view["dealer"] == 0
    assert "hand" not in view


def test_manual_next_dealer_authorized_without_realtime(monkeypatch):
    from types import SimpleNamespace

    from preferans.online.store import FirestoreRooms, StoreError
    from test_auto_deal_store import settle_passout
    from test_secure_rooms import FakeDB, transactional

    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    api = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    rid = api.create("a", "polish-create", require_ready=True)["room_id"]
    api.join(rid, "b", "polish-join-b", 0)
    api.join(rid, "c", "polish-join-c", 1)
    api.command(rid, "a", "polish-config", 2, "lobby_config", {"dealer": 0, "target": 20})
    for i, uid in enumerate("abc"):
        api.command(rid, uid, f"polish-ready-{i}", 3 + i, "lobby_ready", {"ready": True})
    api.start(rid, "a", "polish-start", 6, False)
    between = settle_passout(api, rid)
    assert between["dealer"] == 0
    with pytest.raises(StoreError) as denied:
        api.start(rid, "c", "polish-denied-start", between["version"], False)
    assert denied.value.code == 403
    api.start(rid, "b", "polish-next-start", between["version"], False)
    assert api.view(rid, "b")["dealer"] == 1


@pytest.mark.parametrize("decision", [DefenseDecision.VIST, DefenseDecision.PASS])
def test_concession_rejects_every_defense_decision(decision):
    state = replace(declaration(), defense=(None, decision, None))
    with pytest.raises(RuleViolation):
        apply_command(state, 0, "without_three", {"bid": BID})
