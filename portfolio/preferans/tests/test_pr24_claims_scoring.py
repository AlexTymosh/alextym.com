from dataclasses import replace

import pytest

from preferans.domain.auction import AuctionAction, Bid, RuleViolation
from preferans.domain.cards import FULL_DECK, Suit, deal
from preferans.domain.claims import can_claim, claim_voters, offer_claim, vote_claim
from preferans.domain.game import (
    DefenseDecision,
    EndReason,
    Phase,
    auction_action,
    legal_play_cards,
    play_card,
    start_game,
)
from preferans.domain.ledger import EntryKind, LedgerEntry, ScoreState
from preferans.domain.reward_routing import passout_options
from preferans.domain.scoring import RewardRoute, settle_game
from preferans.online.codec import decode, encode
from preferans.online.views import seat_view
from test_scoring import ledger, passouts, played


@pytest.mark.parametrize("hill,remaining,vists", [(6, 2, 0), (2, 0, 10), (0, 0, 20)])
def test_user_example_blocked_priority_never_redirects_to_lower_pool(hill, remaining, vists):
    game = played(
        7,
        (9, 1, 0),
        (None, DefenseDecision.VIST, DefenseDecision.PASS),
        contract=Bid.regular(7, Suit.SPADES),
    )
    start = ledger(pool=(20, 15, 10), hill=(hill, 0, 0))
    actual = settle_game(start, game, "pr24-block")
    assert actual.pool == start.pool
    assert actual.hill == (remaining, 4, 0)
    assert actual.vists[0][1:] == (vists, vists)
    assert actual.vists[1][0] == 8
    assert start.hill[0] == hill


def test_equal_priority_excludes_only_penalised_player():
    game = played(7, (9, 1, 0), (None, DefenseDecision.VIST, DefenseDecision.PASS))
    actual = settle_game(ledger(pool=(20, 15, 15), hill=(6, 0, 0)), game, "tie")
    assert actual.pool == (20, 15, 19)
    assert actual.hill == (6, 4, 0)
    assert actual.vists[0][1:] == (0, 40)


def test_old_hill_and_current_counter_are_not_outcome_penalties():
    game = played(7, (7, 2, 1))
    entry = LedgerEntry(1, "same-deal", EntryKind.HILL, 1, 12, "counter_penalty")
    score = replace(ledger(pool=(20, 15, 10), hill=(0, 12, 0)), entries=(entry,))
    out = settle_game(score, game, "same-deal")
    assert out.pool == (20, 19, 10) and out.hill[1] == 12
    assert out.vists[0][1] == 40


def test_passout_blocked_help_is_mandatory_hill_then_vists():
    game = passouts((0, 4, 6), level=8)
    start = ledger(pool=(20, 15, 10), hill=(2, 0, 0), passout=8)
    opts = passout_options(start, game)
    assert opts["passout_pending"] == []
    actual = settle_game(
        start,
        game,
        "passout-block",
        passout_routes=(RewardRoute.HELP, RewardRoute.POOL, RewardRoute.POOL),
    )
    assert actual.pool == (20, 15, 10)
    assert actual.hill == (0, 12, 18)
    assert actual.vists[0][1:] == (5, 5)


def test_two_zero_players_can_help_each_other_after_own_credits():
    game = passouts((0, 0, 10), level=8)
    start = ledger(pool=(20, 15, 5), hill=(3, 0, 0), passout=8)
    opts = passout_options(start, game)
    assert opts["passout_pending"] == [0] and opts["passout_targets"][0] == [1]
    out = settle_game(
        start,
        game,
        "two-zero-help",
        passout_routes=(RewardRoute.HELP, RewardRoute.POOL, RewardRoute.POOL),
    )
    assert out.pool == (20, 20, 5)
    assert out.hill == (2, 0, 30)
    assert out.vists[0][1:] == (20, 0)
    other = settle_game(
        start,
        game,
        "two-zero-hill",
        passout_routes=(RewardRoute.HILL_FIRST, RewardRoute.POOL, RewardRoute.POOL),
    )
    assert other.pool == (20, 18, 5) and other.hill[0] == 0


def regular():
    return replace(
        start_game(deal(FULL_DECK, 2)),
        phase=Phase.PLAY,
        turn=0,
        declarer=0,
        contract=Bid.regular(7, Suit.SPADES),
        defense=(None, DefenseDecision.VIST, DefenseDecision.PASS),
    )


def passout():
    state = start_game(deal(FULL_DECK, 2))
    for _ in range(3):
        state = auction_action(state, state.turn, AuctionAction.pass_turn())
    return state


def test_voters_derive_from_final_defense_and_contract():
    state = regular()
    assert claim_voters(state, 0) == {1}
    assert claim_voters(state, 1) == {0}
    assert claim_voters(state, 2) == {0, 1}
    both = replace(state, defense=(None, DefenseDecision.VIST, DefenseDecision.VIST))
    assert claim_voters(both, 0) == {1, 2}
    assert claim_voters(both, 1) == {0, 2}
    for i in range(3):
        assert claim_voters(passout(), i) == set(range(3)) - {i}
        assert claim_voters(replace(state, contract=Bid.misere()), i) == set(range(3)) - {i}


def test_acceptance_does_not_fabricate_tricks_and_settles_normally():
    state = regular()
    state = play_card(state, 0, legal_play_cards(state, 0)[0])
    offer = offer_claim(state, 0)  # It is another player's turn.
    assert not legal_play_cards(offer, 1)
    with pytest.raises(RuleViolation):
        vote_claim(offer, 2, True)  # Passing defender has no vote on declarer's offer.
    finished = vote_claim(offer, 1, True)
    assert finished.end_reason == EndReason.ALL_MINE_ACCEPTED
    assert finished.completed_tricks == state.completed_tricks == ()
    assert finished.tricks_won == (10, 0, 0)
    assert finished.claim.partial == state.trick
    assert not any(finished.hands)
    assert settle_game(ScoreState.new(), finished, "claimed").hill == (0, 8, 0)
    assert settle_game(ScoreState.new(), finished, "claimed").pool == (4, 0, 0)
    with pytest.raises(RuleViolation):
        settle_game(
            ScoreState.new(),
            replace(finished, claim=replace(finished.claim, approved=frozenset())),
            "forged",
        )


def test_refusal_restores_partial_trick_and_reoffer_waits_for_next_trick():
    state = regular()
    state = play_card(state, 0, legal_play_cards(state, 0)[0])
    offer = offer_claim(state, 2)
    one = vote_claim(offer, 0, True)
    with pytest.raises(RuleViolation):
        vote_claim(one, 0, True)
    refused = vote_claim(one, 1, False)
    assert replace(refused, claim=None) == state
    assert not can_claim(refused, 2)
    for _ in range(2):
        owner = refused.turn
        refused = play_card(
            refused, refused.controllers[owner], legal_play_cards(refused, owner)[0]
        )
    assert can_claim(refused, 2)


def test_projection_privacy_and_old_state_codec():
    state = passout()
    old = encode(state)
    del old["fields"]["claim"]
    del old["fields"]["misere_votes"]
    assert decode(old) == state
    offer = offer_claim(state, 1)
    assert decode(encode(offer)) == offer
    room = {
        "id": "a" * 32,
        "status": "playing",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "deal",
    }
    for uid in "abc":
        view = seat_view(room, offer, ScoreState.new(), uid, 1)
        assert len(view["claim"]["cards"]) == 10 and view["claim"]["seat"] == 1
        assert not view["legal_cards"] and not view.get("can_claim")
        assert not view["open_hands"]
    observer = seat_view(room, offer, ScoreState.new(), "observer", 1, owner=True)
    assert "claim" not in observer and "hand" not in observer
    denied = vote_claim(offer, 0, False)
    assert seat_view(room, denied, ScoreState.new(), "c", 2)["claim"]["cards"] == []
