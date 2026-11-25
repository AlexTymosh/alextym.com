from dataclasses import replace

import pytest

from preferans.domain.auction import (
    AuctionAction,
    AuctionOutcome,
    Bid,
    RuleViolation,
    apply_auction_action,
    can_say_here,
    start_auction,
)
from preferans.domain.cards import FULL_DECK, Suit, deal
from preferans.domain.game import (
    EndReason,
    Phase,
    auction_action,
    discard_cards,
    offer_misere,
    start_game,
    vote_misere,
)
from preferans.domain.ledger import ScoreState
from preferans.domain.scoring import settle_game
from preferans.online.codec import decode, encode
from preferans.online.commands import apply_command
from preferans.online.views import seat_view


@pytest.mark.parametrize("dealer", [0, 1, 2])
def test_third_after_bid_pass_can_hold_repeatedly(dealer):
    a, b, c = ((dealer + n) % 3 for n in (1, 2, 3))
    state = start_auction(dealer)
    state = apply_auction_action(state, a, AuctionAction.place(Bid.regular(6, Suit.CLUBS)))
    assert not can_say_here(state, b)
    state = apply_auction_action(state, b, AuctionAction.pass_turn())
    assert can_say_here(state, c)
    state = apply_auction_action(state, c, AuctionAction.here())
    assert state.high_bidder == c
    assert not can_say_here(state, a)
    state = apply_auction_action(state, a, AuctionAction.place(Bid.regular(7, Suit.SPADES)))
    assert can_say_here(state, c)
    state = apply_auction_action(state, c, AuctionAction.here())
    state = apply_auction_action(state, a, AuctionAction.pass_turn())
    assert state.outcome == AuctionOutcome.WON and state.high_bidder == c


def test_obligatory_bid_and_no_prior_bid_before_pass():
    state = start_auction(2)
    state = apply_auction_action(state, 0, AuctionAction.place(Bid.regular(6, Suit.SPADES)))
    state = apply_auction_action(state, 1, AuctionAction.pass_turn())
    assert not can_say_here(state, 2)
    with pytest.raises(RuleViolation):
        apply_auction_action(state, 2, AuctionAction.here())
    other = apply_auction_action(start_auction(2), 0, AuctionAction.pass_turn())
    other = apply_auction_action(other, 1, AuctionAction.place(Bid.regular(7, Suit.CLUBS)))
    assert not can_say_here(other, 2)


def ready():
    state = start_game(deal(FULL_DECK, 2))
    state = auction_action(state, 0, AuctionAction.place(Bid.misere()))
    state = auction_action(state, 1, AuctionAction.pass_turn())
    state = auction_action(state, 2, AuctionAction.pass_turn())
    return discard_cards(state, 0, state.widow)


@pytest.mark.parametrize("first", [1, 2])
def test_two_approvals_settle_without_inventing_tricks(first):
    state = offer_misere(ready(), 0)
    assert state.phase == Phase.MISERE_OFFER
    state = vote_misere(state, first, True)
    assert state.phase == Phase.MISERE_OFFER
    with pytest.raises(RuleViolation):
        vote_misere(state, first, True)
    state = vote_misere(state, 3 - first, True)
    assert state.phase == Phase.FINISHED and state.end_reason == EndReason.MISERE_ACCEPTED
    assert state.completed_tricks == () and state.tricks_won == (0, 0, 0)
    score = settle_game(ScoreState.new(), state, "accepted-misere")
    assert score.pool == (10, 0, 0) and score.hill == (0, 0, 0)
    with pytest.raises(RuleViolation):
        settle_game(score, state, "accepted-misere")
    with pytest.raises(RuleViolation):
        settle_game(ScoreState.new(), replace(state, misere_votes=frozenset({first})), "forged")


def test_reject_restores_normal_play_and_forbids_reoffer():
    state = offer_misere(ready(), 0)
    with pytest.raises(RuleViolation):
        vote_misere(state, 0, True)
    with pytest.raises(RuleViolation):
        apply_command(state, 1, "misere_vote", {"approve": "yes"})
    state = vote_misere(state, 1, True)
    state = vote_misere(state, 2, False)
    assert state.phase == Phase.PLAY and state.turn == state.first_hand
    assert 0 not in state.exposed_hands and not state.misere_votes
    with pytest.raises(RuleViolation):
        offer_misere(state, 0)


def test_projection_only_reveals_declarer_to_members_and_legacy_codec():
    state = ready()
    old = encode(state)
    del old["fields"]["misere_votes"]
    assert decode(old) == state
    state = offer_misere(state, 0)
    assert decode(encode(state)) == state
    room = {
        "id": "a" * 32,
        "status": "playing",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "g",
    }
    for uid in ("b", "c"):
        view = seat_view(room, state, ScoreState.new(), uid, 1)
        assert view["misere_offer"]["can_vote"]
        assert [h["seat"] for h in view["open_hands"]] == [0]
        assert len(view["open_hands"][0]["cards"]) == 10
        assert "own_discard" not in view
    observer = seat_view(room, state, ScoreState.new(), "observer", 1, owner=True)
    assert not observer["open_hands"] and "misere_offer" not in observer
    rejected = vote_misere(state, 1, False)
    assert all(
        h["seat"] != 0 for h in seat_view(room, rejected, ScoreState.new(), "b", 2)["open_hands"]
    )
