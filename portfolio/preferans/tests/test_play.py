from __future__ import annotations

from preferans.domain import Card, Rank, Suit, legal_cards, winning_card
from preferans.domain.play import PlayedCard


def card(rank: Rank, suit: Suit) -> Card:
    return Card(suit, rank)


def test_follow_suit_over_trump() -> None:
    hand = (card(Rank.SEVEN, Suit.CLUBS), card(Rank.ACE, Suit.SPADES))
    assert legal_cards(hand, Suit.CLUBS, Suit.SPADES) == hand[:1]


def test_trump_mandatory_but_not_overtrump() -> None:
    hand = (
        card(Rank.SEVEN, Suit.SPADES),
        card(Rank.ACE, Suit.SPADES),
        card(Rank.NINE, Suit.HEARTS),
    )
    assert legal_cards(hand, Suit.DIAMONDS, Suit.SPADES) == hand[:2]


def test_no_suit_no_trump_can_play_anything() -> None:
    hand = (card(Rank.SEVEN, Suit.CLUBS), card(Rank.ACE, Suit.HEARTS))
    assert legal_cards(hand, Suit.DIAMONDS, Suit.SPADES) == hand


def test_forced_widow_suit_overrides_actual_lead_without_trumping() -> None:
    heart = card(Rank.SEVEN, Suit.HEARTS)
    hand = (card(Rank.ACE, Suit.CLUBS), heart)
    assert legal_cards(hand, Suit.CLUBS, forced_suit=Suit.HEARTS) == (heart,)
    assert legal_cards(hand[:1], Suit.CLUBS, forced_suit=Suit.HEARTS) == hand[:1]


def test_highest_trump_wins_regardless_of_lead_rank() -> None:
    plays = (
        PlayedCard(0, 0, card(Rank.ACE, Suit.CLUBS)),
        PlayedCard(1, 1, card(Rank.SEVEN, Suit.SPADES)),
        PlayedCard(2, 2, card(Rank.TEN, Suit.SPADES)),
    )
    assert winning_card(plays, Suit.SPADES) == (2, Suit.CLUBS)


def test_forced_widow_suit_wins_even_if_first_hand_disagrees() -> None:
    plays = (
        PlayedCard(1, 1, card(Rank.SEVEN, Suit.CLUBS)),
        PlayedCard(2, 2, card(Rank.ACE, Suit.CLUBS)),
        PlayedCard(0, 0, card(Rank.TEN, Suit.HEARTS)),
    )
    assert winning_card(plays, trump=None, forced_suit=Suit.HEARTS) == (0, Suit.HEARTS)


def test_all_void_forced_suit_has_explicit_technical_fallback() -> None:
    plays = (
        PlayedCard(1, 1, card(Rank.SEVEN, Suit.CLUBS)),
        PlayedCard(2, 2, card(Rank.ACE, Suit.CLUBS)),
        PlayedCard(0, 0, card(Rank.TEN, Suit.SPADES)),
    )
    assert winning_card(plays, trump=None, forced_suit=Suit.HEARTS) == (2, Suit.CLUBS)
