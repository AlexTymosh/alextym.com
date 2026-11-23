from __future__ import annotations

from dataclasses import replace

import pytest

from preferans.domain import (
    BID_ORDER,
    AuctionAction,
    AuctionOutcome,
    Bid,
    BidKind,
    RuleViolation,
    Suit,
    apply_auction_action,
    can_say_here,
    legal_auction_bids,
    legal_final_contracts,
    replay_auction,
    start_auction,
)


B = AuctionAction.place
P = AuctionAction.pass_turn()
H = AuctionAction.here()


def test_32_bid_rank_order_and_special_tiers() -> None:
    assert len(BID_ORDER) == len(set(BID_ORDER)) == 32
    assert [b.ordinal for b in BID_ORDER] == list(range(32))
    assert BID_ORDER[0] == Bid.regular(6, Suit.SPADES)
    assert BID_ORDER[4] == Bid.regular(6, None)
    assert BID_ORDER[14] == Bid.regular(8, None)
    assert BID_ORDER[15] == Bid.misere()
    assert BID_ORDER[16] == Bid.regular(9, Suit.SPADES)
    assert BID_ORDER[21] == Bid.misere_no_widow()
    assert BID_ORDER[22] == Bid.regular(10, Suit.SPADES)
    assert BID_ORDER[26] == Bid.regular(10, None)
    assert BID_ORDER[27] == Bid.ten_no_widow(Suit.SPADES)
    assert BID_ORDER[31] == Bid.ten_no_widow(None)


@pytest.mark.parametrize(
    "bid",
    [
        lambda: Bid.regular(5, Suit.SPADES),
        lambda: Bid.regular(11, Suit.SPADES),
        lambda: Bid(BidKind.MISERE, 9),
        lambda: Bid(BidKind.TEN_NO_WIDOW, 9, Suit.CLUBS),
        lambda: Bid.regular(6, "invalid"),
    ],
)
def test_bad_bids_cannot_be_constructed(bid) -> None:
    with pytest.raises(ValueError):
        bid()


@pytest.mark.parametrize("level", [6, 7, 8])
def test_passout_minimum_level(level: int) -> None:
    state = start_auction(0, level)
    legal = legal_auction_bids(state, 1)
    assert all(b.level >= level for b in legal if b.kind == BidKind.REGULAR)
    assert Bid.misere() in legal
    assert Bid.ten_no_widow(None) in legal
    assert Bid.regular(level, Suit.SPADES) in legal


def test_initial_six_spades_and_all_passout() -> None:
    state = start_auction(0)
    assert state.turn == 1
    for actor in (1, 2, 0):
        state = apply_auction_action(state, actor, P)
    assert state.outcome == AuctionOutcome.PASSOUT
    assert state.turn is None
    with pytest.raises(RuleViolation):
        apply_auction_action(state, 1, B(Bid.regular(6, Suit.SPADES)))


def test_winner_pass_and_out_of_turn_rejected() -> None:
    state = start_auction(0)
    with pytest.raises(RuleViolation):
        apply_auction_action(state, 0, P)
    state = apply_auction_action(state, 1, B(Bid.regular(7, Suit.CLUBS)))
    state = apply_auction_action(state, 2, P)
    assert state.turn == 0
    with pytest.raises(RuleViolation):
        apply_auction_action(state, 2, B(Bid.regular(9, Suit.CLUBS)))
    state = apply_auction_action(state, 0, P)
    assert state.outcome == AuctionOutcome.WON
    assert state.high_bidder == 1


def test_first_hand_here_retains_equal_seven_clubs() -> None:
    state = start_auction(0)
    state = apply_auction_action(state, 1, B(Bid.regular(7, Suit.SPADES)))
    state = apply_auction_action(state, 2, B(Bid.regular(7, Suit.CLUBS)))
    state = apply_auction_action(state, 0, P)
    assert can_say_here(state, 1)
    state = apply_auction_action(state, 1, H)
    assert state.high_bid == Bid.regular(7, Suit.CLUBS)
    assert state.high_bidder == 1
    assert state.turn == 2
    assert Bid.regular(7, Suit.CLUBS) not in legal_auction_bids(state, 2)
    assert Bid.regular(7, Suit.DIAMONDS) in legal_auction_bids(state, 2)
    state = apply_auction_action(state, 2, P)
    assert state.outcome == AuctionOutcome.WON
    assert state.high_bidder == 1


def test_here_never_allowed_for_six_spades_or_other_seat() -> None:
    st = start_auction(0)
    st = replace(st, turn=1, high_bid=Bid.regular(6, Suit.SPADES), high_bidder=2)
    assert not can_say_here(st, 1)
    with pytest.raises(RuleViolation):
        apply_auction_action(st, 1, H)
    st = replace(st, turn=2, high_bid=Bid.regular(7, Suit.CLUBS), high_bidder=0)
    assert not can_say_here(st, 2)


def test_misere_can_only_be_first_personal_bid() -> None:
    st = start_auction(0)
    st = apply_auction_action(st, 1, B(Bid.regular(6, Suit.SPADES)))
    st = apply_auction_action(st, 2, B(Bid.regular(7, Suit.SPADES)))
    st = apply_auction_action(st, 0, P)
    assert Bid.misere() not in legal_auction_bids(st, 1)
    with pytest.raises(RuleViolation):
        apply_auction_action(st, 1, B(Bid.misere()))


def test_misere_without_widow_requires_prior_personal_misere_and_nine_overbid() -> None:
    st = start_auction(0)
    st = apply_auction_action(st, 1, B(Bid.misere()))
    st = apply_auction_action(st, 2, B(Bid.regular(9, Suit.SPADES)))
    assert Bid.misere_no_widow() not in legal_auction_bids(st, 0)
    st = apply_auction_action(st, 0, P)
    assert Bid.misere_no_widow() in legal_auction_bids(st, 1)
    st = apply_auction_action(st, 1, B(Bid.misere_no_widow()))
    assert st.high_bid.ordinal == 21
    assert Bid.regular(10, Suit.SPADES) in legal_auction_bids(st, 2)


def test_ten_no_widow_can_open_and_be_overbid_by_higher_suit() -> None:
    st = start_auction(0)
    st = apply_auction_action(st, 1, B(Bid.ten_no_widow(Suit.SPADES)))
    assert Bid.ten_no_widow(Suit.CLUBS) in legal_auction_bids(st, 2)
    st = apply_auction_action(st, 2, B(Bid.ten_no_widow(Suit.CLUBS)))
    assert st.high_bidder == 2
    assert Bid.ten_no_widow(Suit.SPADES) not in legal_auction_bids(st, 0)


def test_top_bid_wins_after_two_passing() -> None:
    st = start_auction(0)
    st = apply_auction_action(st, 1, B(Bid.ten_no_widow(None)))
    st = apply_auction_action(st, 2, P)
    st = apply_auction_action(st, 0, P)
    assert st.outcome == AuctionOutcome.WON
    assert st.high_bid == Bid.ten_no_widow(None)


def test_final_contract_is_same_bid_class_and_not_below_floor() -> None:
    floor = Bid.regular(7, Suit.CLUBS)
    legal = legal_final_contracts(floor)
    assert Bid.regular(7, Suit.SPADES) not in legal
    assert Bid.regular(7, Suit.CLUBS) in legal
    assert Bid.regular(7, None) in legal
    assert Bid.regular(8, Suit.SPADES) in legal
    assert Bid.regular(10, None) in legal
    assert Bid.misere() not in legal
    assert Bid.ten_no_widow(Suit.SPADES) not in legal
    no_widow = legal_final_contracts(Bid.ten_no_widow(Suit.CLUBS))
    stronger_suits = (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, None)
    assert no_widow == tuple(Bid.ten_no_widow(suit) for suit in stronger_suits)
    assert legal_final_contracts(Bid.misere()) == (Bid.misere(),)


def test_auction_replay_from_immutable_events() -> None:
    st = start_auction(2)
    st = apply_auction_action(st, 0, B(Bid.regular(8, Suit.SPADES)))
    st = apply_auction_action(st, 1, B(Bid.regular(9, Suit.SPADES)))
    st = apply_auction_action(st, 2, P)
    st = apply_auction_action(st, 0, P)
    assert replay_auction(2, st.history) == st
