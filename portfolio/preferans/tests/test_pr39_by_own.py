from dataclasses import replace

import pytest

from preferans.domain.auction import Bid, RuleViolation
from preferans.domain.cards import Suit
from preferans.domain.claims import by_own_options, offer_claim, vote_claim
from preferans.domain.game import DefenseDecision, Phase, legal_play_cards, play_card
from preferans.domain.ledger import ScoreState
from preferans.domain.scoring import settle_game
from preferans.online.codec import decode, encode
from preferans.online.commands import apply_command
from preferans.online.views import seat_view
from test_pr24_claims_scoring import regular


@pytest.mark.parametrize("level,options", [(6, (4,)), (7, (2, 3)), (8, (1, 2)), (9, (1,))])
def test_by_own_agreement_uses_existing_scoring(level, options):
    state = replace(regular(), contract=Bid.regular(level, Suit.HEARTS))
    assert by_own_options(state, 0) == options
    assert by_own_options(state, 1) == by_own_options(state, 2) == ()
    for target in options:
        pending = apply_command(state, 0, "claim_offer", {"defender_target": target})
        assert pending.claim_pending
        assert pending.claim.display_order == ()
        assert decode(encode(pending)) == pending
        legacy = encode(offer_claim(state, 0))
        del legacy["fields"]["claim"]["fields"]["defender_target"]
        assert decode(legacy) == offer_claim(state, 0)
        with pytest.raises(RuleViolation):
            vote_claim(pending, 2, True)
        finished = vote_claim(pending, 1, True)
        assert finished.phase == Phase.FINISHED
        assert finished.tricks_won == (10 - target, target, 0)
        assert finished.completed_tricks == state.completed_tricks
        score = settle_game(ScoreState.new(), finished, f"by-own-{level}-{target}")
        assert score.pool[0] > 0
        assert score.hill == (0, 0, 0)
        with pytest.raises(RuleViolation):
            settle_game(
                ScoreState.new(),
                replace(finished, tricks_won=(10, 0, 0)),
                "forged",
            )
        with pytest.raises(RuleViolation):
            vote_claim(finished, 1, True)


def test_by_own_rejects_wrong_contract_actor_or_target():
    state = regular()
    for contract in (Bid.regular(6, Suit.SPADES), Bid.regular(10, Suit.HEARTS), Bid.misere()):
        assert by_own_options(replace(state, contract=contract), 0) == ()
    assert (
        by_own_options(
            replace(state, defense=(None, DefenseDecision.VIST, DefenseDecision.VIST)), 0
        )
        == ()
    )
    assert by_own_options(replace(state, phase=Phase.DEFENSE_SECOND), 0) == ()
    for seat, target in ((1, 2), (2, 3), (0, 1), (0, 4), (0, True)):
        with pytest.raises(RuleViolation):
            offer_claim(state, seat, defender_target=target)
    for args in (
        {"defender_target": None},
        {"defender_target": True},
        {"defender_target": 2, "cards": []},
    ):
        with pytest.raises(RuleViolation):
            apply_command(state, 0, "claim_offer", args)


def test_by_own_refusal_preserves_partial_and_projection_reveals_only_claimant():
    state = regular()
    state = play_card(state, 0, legal_play_cards(state, 0)[0])
    pending = offer_claim(state, 0, defender_target=3)
    room = {
        "id": "a" * 32,
        "status": "playing",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "deal",
    }
    for uid in "abc":
        view = seat_view(room, pending, ScoreState.new(), uid, 1)
        assert view["claim"]["cards"] == [
            {"rank": int(card.rank), "suit": card.suit.value} for card in state.hands[0]
        ]
        assert view["claim"]["voters"] == [1]
        assert view["claim"]["defender_target"] == 3
        assert "by_own_options" not in view
    refused = vote_claim(pending, 1, False)
    assert replace(refused, claim=None) == state
    assert by_own_options(refused, 0) == ()
    for uid in "abc":
        assert seat_view(room, refused, ScoreState.new(), uid, 2)["claim"]["cards"] == []
    observer = seat_view(room, pending, ScoreState.new(), "observer", 1, owner=True)
    assert "claim" not in observer
    accepted = vote_claim(pending, 1, True)
    assert accepted.claim.partial == state.trick
    assert accepted.tricks_won == (7, 3, 0)
    finished_view = seat_view(
        {**room, "status": "awaiting_settlement"}, accepted, ScoreState.new(), "a", 2
    )
    assert finished_view["claim"]["awards"] == [7, 3, 0]
    assert finished_view["claim"]["cards"] == []


def test_already_played_tricks_are_preserved():
    state = regular()
    for _ in range(3):
        owner = state.turn
        state = play_card(state, state.controllers[owner], legal_play_cards(state, owner)[0])
    if 3 not in by_own_options(state, 0):
        assert state.completed_tricks[0].winner == 2
        assert by_own_options(state, 0) == (2,)
        return
    finished = vote_claim(offer_claim(state, 0, defender_target=3), 1, True)
    assert finished.completed_tricks == state.completed_tricks
    assert finished.tricks_won == (7, 3, 0)
