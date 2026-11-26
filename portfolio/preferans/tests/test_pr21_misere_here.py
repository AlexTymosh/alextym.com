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


def test_projection_reveals_other_defender_only_to_defenders_and_legacy_codec():
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
        expected = [0, 2 if uid == "b" else 1]
        assert [h["seat"] for h in view["open_hands"]] == expected
        for hand in view["open_hands"]:
            assert len(hand["cards"]) == 10
            assert {(c["suit"], c["rank"]) for c in hand["cards"]} == {
                (c.suit.value, c.rank.value) for c in state.hands[hand["seat"]]
            }
        assert "own_discard" not in view
    declarer = seat_view(room, state, ScoreState.new(), "a", 1)
    assert declarer["open_hands"] == []
    assert not declarer["misere_offer"]["can_vote"]
    observer = seat_view(room, state, ScoreState.new(), "observer", 1, owner=True)
    assert not observer["open_hands"] and "misere_offer" not in observer
    rejected = vote_misere(state, 1, False)
    assert all(
        h["seat"] != 0 for h in seat_view(room, rejected, ScoreState.new(), "b", 2)["open_hands"]
    )


@pytest.mark.parametrize("bid", [Bid.misere(), Bid.misere_no_widow()])
def test_misere_cannot_be_held_even_with_here_right(bid):
    state = start_auction(2)
    state = apply_auction_action(state, 0, AuctionAction.place(Bid.misere()))
    state = apply_auction_action(state, 1, AuctionAction.pass_turn())
    if bid == Bid.misere_no_widow():
        state = apply_auction_action(state, 2, AuctionAction.place(Bid.regular(9, Suit.SPADES)))
        state = apply_auction_action(state, 0, AuctionAction.place(bid))
    assert state.high_bid == bid and state.turn == 2
    assert not can_say_here(state, 2)
    with pytest.raises(RuleViolation):
        apply_auction_action(state, 2, AuctionAction.here())


def test_final_notebook_uses_signed_pairwise_results():
    from preferans.domain.settlement import net_results, pairwise_results

    game = vote_misere(vote_misere(offer_misere(ready(), 0), 1, True), 2, True)
    initial = ScoreState.new()
    score = replace(
        initial,
        pool=(initial.target,) * 3,
        closed=True,
        hill=(0, 3, 6),
        vists=((0, 8, 4), (0, 0, 0), (0, 0, 0)),
    )
    room = {
        "id": "a" * 32,
        "status": "closed",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "g",
    }
    pairs = pairwise_results(score)
    assert pairs == ((0, 18, 24), (-18, 0, 10), (-24, -10, 0))
    assert net_results(score) == (42, -8, -34)
    for uid in "abc":
        final = seat_view(room, game, score, uid, 1)["final_settlement"]
        assert final == {"pairs": [list(row) for row in pairs], "net": [42, -8, -34]}
    assert "final_settlement" not in seat_view(room, game, score, "observer", 1, owner=True)
    assert "final_settlement" not in seat_view({**room, "sheet_loser": 1}, game, score, "a", 1)
