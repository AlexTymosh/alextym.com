"""Immutable card primitives and historical packet dealing order.

The caller provides entropy. Never serialize a shuffled deck to an untrusted view.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Protocol, Sequence


class Suit(str, Enum):
    SPADES = "S"
    CLUBS = "C"
    DIAMONDS = "D"
    HEARTS = "H"


class Rank(IntEnum):
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14


SUITS: tuple[Suit, ...] = tuple(Suit)
RANKS: tuple[Rank, ...] = tuple(Rank)


@dataclass(frozen=True, slots=True)
class Card:
    suit: Suit
    rank: Rank

    def __post_init__(self) -> None:
        if not isinstance(self.suit, Suit) or not isinstance(self.rank, Rank):
            raise ValueError("Invalid card suit or rank")

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"


FULL_DECK: tuple[Card, ...] = tuple(Card(suit, rank) for suit in SUITS for rank in RANKS)


class Shuffler(Protocol):
    def shuffle(self, x: list[Card]) -> None: ...


def shuffled_deck(rng: Shuffler | None = None) -> tuple[Card, ...]:
    """Use OS-backed randomness in production; inject a seeded RNG in tests."""
    cards = list(FULL_DECK)
    (rng if rng is not None else secrets.SystemRandom()).shuffle(cards)
    return tuple(cards)


@dataclass(frozen=True, slots=True)
class Deal:
    hands: tuple[tuple[Card, ...], tuple[Card, ...], tuple[Card, ...]]
    widow: tuple[Card, Card]
    dealer: int
    first_hand: int


def deal(deck: Sequence[Card], dealer: int) -> Deal:
    """2 cards per seat; 2-card widow; four more 2-card rounds per seat."""
    if type(dealer) is not int or dealer not in (0, 1, 2):
        raise ValueError("Dealer must be a seat between 0 and 2")
    if len(deck) != 32 or len(set(deck)) != 32 or set(deck) != set(FULL_DECK):
        raise ValueError("Deal requires exactly the 32 unique Preferans cards")
    first = (dealer + 1) % 3
    seats = tuple((first + i) % 3 for i in range(3))
    hands: list[list[Card]] = [[], [], []]
    offset = 0
    for seat in seats:
        hands[seat].extend(deck[offset : offset + 2])
        offset += 2
    widow = (deck[offset], deck[offset + 1])
    offset += 2
    for _ in range(4):
        for seat in seats:
            hands[seat].extend(deck[offset : offset + 2])
            offset += 2
    assert offset == 32
    return Deal(tuple(tuple(hand) for hand in hands), widow, dealer, first)
