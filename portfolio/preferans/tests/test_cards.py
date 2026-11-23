from __future__ import annotations

import random

import pytest

from preferans.domain import Card, FULL_DECK, Rank, Suit, deal, shuffled_deck


def test_deck_is_32_unique_cards() -> None:
    assert len(FULL_DECK) == len(set(FULL_DECK)) == 32
    assert all(sum(c.suit == suit for c in FULL_DECK) == 8 for suit in Suit)
    assert all(sum(c.rank == rank for c in FULL_DECK) == 4 for rank in Rank)


@pytest.mark.parametrize("dealer", [0, 1, 2])
def test_packet_deal_rounds_and_widow_position(dealer: int) -> None:
    result = deal(FULL_DECK, dealer)
    first, second, third = ((dealer + n) % 3 for n in (1, 2, 3))
    assert result.first_hand == first
    assert result.hands[first][:2] == FULL_DECK[0:2]
    assert result.hands[second][:2] == FULL_DECK[2:4]
    assert result.hands[third][:2] == FULL_DECK[4:6]
    assert result.widow == tuple(FULL_DECK[6:8])
    assert result.hands[first][2:4] == FULL_DECK[8:10]
    assert result.hands[second][2:4] == FULL_DECK[10:12]
    assert all(len(hand) == 10 for hand in result.hands)
    dealt = (*result.hands[0], *result.hands[1], *result.hands[2], *result.widow)
    assert set(dealt) == set(FULL_DECK)


def test_seeded_shuffle_is_reproducible_but_not_default_order() -> None:
    a = shuffled_deck(random.Random(42))
    b = shuffled_deck(random.Random(42))
    assert a == b and a != FULL_DECK and set(a) == set(FULL_DECK)


@pytest.mark.parametrize("bad", [(0,) * 32, FULL_DECK[:31], (*FULL_DECK[:-1], FULL_DECK[0])])
def test_invalid_deck_rejected(bad: tuple) -> None:
    with pytest.raises(ValueError):
        deal(bad, 0)


@pytest.mark.parametrize("dealer", [-1, 3, True, 1.5])
def test_invalid_dealer_rejected(dealer: object) -> None:
    with pytest.raises(ValueError):
        deal(FULL_DECK, dealer)


def test_cards_validate_rank_and_suit() -> None:
    with pytest.raises(ValueError):
        Card(Suit.SPADES, 6)
    with pytest.raises(ValueError):
        Card("X", Rank.ACE)
