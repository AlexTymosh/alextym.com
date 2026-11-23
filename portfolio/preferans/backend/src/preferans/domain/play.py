"""Pure card legality and trick resolution, including special passout leads."""

from __future__ import annotations

from dataclasses import dataclass

from .auction import RuleViolation
from .cards import Card, Suit


@dataclass(frozen=True, slots=True)
class PlayedCard:
    owner: int
    actor: int
    card: Card


@dataclass(frozen=True, slots=True)
class CompletedTrick:
    number: int
    cards: tuple[PlayedCard, PlayedCard, PlayedCard]
    winner: int
    effective_suit: Suit


def legal_cards(
    hand: tuple[Card, ...],
    led_suit: Suit | None,
    trump: Suit | None = None,
    forced_suit: Suit | None = None,
) -> tuple[Card, ...]:
    """Passouts use the widow suit; ordinary games enforce compulsory trump."""
    if forced_suit is not None:
        matching = tuple(card for card in hand if card.suit == forced_suit)
        return matching if matching else hand
    if led_suit is None:
        return hand
    matching = tuple(card for card in hand if card.suit == led_suit)
    if matching:
        return matching
    if trump is not None:
        trumps = tuple(card for card in hand if card.suit == trump)
        if trumps:
            return trumps
    return hand


def winning_card(
    cards: tuple[PlayedCard, PlayedCard, PlayedCard],
    trump: Suit | None,
    forced_suit: Suit | None = None,
) -> tuple[int, Suit]:
    if len(cards) != 3 or len({play.owner for play in cards}) != 3:
        raise RuleViolation("A trick needs three distinct seats")
    if trump is not None and forced_suit is not None:
        raise RuleViolation("Passouts cannot have trump")
    effective = forced_suit if forced_suit is not None else cards[0].card.suit
    if forced_suit is not None and not any(play.card.suit == forced_suit for play in cards):
        # Explicit engineering fallback pending a separately confirmed house example.
        effective = cards[0].card.suit
    trump_cards = [play for play in cards if trump is not None and play.card.suit == trump]
    pool = trump_cards if trump_cards else [play for play in cards if play.card.suit == effective]
    if not pool:
        raise AssertionError("No matching card in completed trick")
    winner = max(pool, key=lambda play: play.card.rank).owner
    return winner, effective
