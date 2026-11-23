"""Pure two-stage Preferans auction. A bid sets a *minimum*, not a contract."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .cards import SUITS, Suit


class RuleViolation(ValueError):
    """A business action is illegal in the current state."""


class BidKind(str, Enum):
    REGULAR = "regular"
    MISERE = "misere"
    MISERE_NO_WIDOW = "misere_no_widow"
    TEN_NO_WIDOW = "ten_no_widow"


@dataclass(frozen=True, slots=True)
class Bid:
    kind: BidKind
    level: int | None = None
    suit: Suit | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BidKind):
            raise ValueError("Unknown bid kind")
        if self.kind == BidKind.REGULAR:
            if type(self.level) is not int or self.level not in range(6, 11):
                raise ValueError("Regular level must be 6..10")
            if self.suit is not None and not isinstance(self.suit, Suit):
                raise ValueError("Unknown suit")
        elif self.kind == BidKind.TEN_NO_WIDOW:
            if self.level != 10 or (self.suit is not None and not isinstance(self.suit, Suit)):
                raise ValueError("No-widow ten must have level 10 and a valid suit")
        elif self.level is not None or self.suit is not None:
            raise ValueError("Misere cannot specify a level or trump")

    @classmethod
    def regular(cls, level: int, suit: Suit | None) -> Bid:
        return cls(BidKind.REGULAR, level, suit)

    @classmethod
    def misere(cls) -> Bid:
        return cls(BidKind.MISERE)

    @classmethod
    def misere_no_widow(cls) -> Bid:
        return cls(BidKind.MISERE_NO_WIDOW)

    @classmethod
    def ten_no_widow(cls, suit: Suit | None) -> Bid:
        return cls(BidKind.TEN_NO_WIDOW, 10, suit)

    @property
    def ordinal(self) -> int:
        return BID_ORDER.index(self)

    @property
    def uses_widow(self) -> bool:
        return self.kind in (BidKind.REGULAR, BidKind.MISERE)


_SUIT_BIDS: tuple[Suit | None, ...] = (*SUITS, None)
BID_ORDER: tuple[Bid, ...] = (
    *(Bid.regular(level, suit) for level in range(6, 9) for suit in _SUIT_BIDS),
    Bid.misere(),
    *(Bid.regular(9, suit) for suit in _SUIT_BIDS),
    Bid.misere_no_widow(),
    *(Bid.regular(10, suit) for suit in _SUIT_BIDS),
    *(Bid.ten_no_widow(suit) for suit in _SUIT_BIDS),
)
assert len(BID_ORDER) == 32


class AuctionActionKind(str, Enum):
    BID = "bid"
    PASS = "pass"
    HERE = "here"


@dataclass(frozen=True, slots=True)
class AuctionAction:
    kind: AuctionActionKind
    bid: Bid | None = None

    @classmethod
    def place(cls, bid: Bid) -> AuctionAction:
        return cls(AuctionActionKind.BID, bid)

    @classmethod
    def pass_turn(cls) -> AuctionAction:
        return cls(AuctionActionKind.PASS)

    @classmethod
    def here(cls) -> AuctionAction:
        return cls(AuctionActionKind.HERE)


@dataclass(frozen=True, slots=True)
class AuctionEvent:
    actor: int
    action: AuctionAction


class AuctionOutcome(str, Enum):
    BIDDING = "bidding"
    WON = "won"
    PASSOUT = "passout"


@dataclass(frozen=True, slots=True)
class AuctionState:
    dealer: int
    first_hand: int
    minimum_level: int
    turn: int | None
    active: frozenset[int]
    high_bid: Bid | None = None
    high_bidder: int | None = None
    made_bid: frozenset[int] = frozenset()
    misere_bidders: frozenset[int] = frozenset()
    history: tuple[AuctionEvent, ...] = ()
    outcome: AuctionOutcome = AuctionOutcome.BIDDING


def start_auction(dealer: int, minimum_level: int = 6) -> AuctionState:
    if type(dealer) is not int or dealer not in (0, 1, 2):
        raise ValueError("Invalid dealer")
    if type(minimum_level) is not int or minimum_level not in (6, 7, 8):
        raise ValueError("Minimum level must be 6, 7 or 8")
    first_hand = (dealer + 1) % 3
    return AuctionState(dealer, first_hand, minimum_level, first_hand, frozenset((0, 1, 2)))


def rank_bid(bid: Bid) -> int:
    return bid.ordinal


def legal_auction_bids(state: AuctionState, actor: int) -> tuple[Bid, ...]:
    if state.outcome != AuctionOutcome.BIDDING or state.turn != actor:
        return ()
    threshold = state.high_bid.ordinal if state.high_bid is not None else -1
    result: list[Bid] = []
    for bid in BID_ORDER:
        if bid.ordinal <= threshold:
            continue
        if bid.kind == BidKind.REGULAR and bid.level is not None:
            if bid.level < state.minimum_level:
                continue
        if bid.kind == BidKind.MISERE and actor in state.made_bid:
            continue
        if bid.kind == BidKind.MISERE_NO_WIDOW and not (
            actor in state.misere_bidders
            and state.high_bid is not None
            and state.high_bid.kind == BidKind.REGULAR
            and state.high_bid.level == 9
        ):
            continue
        result.append(bid)
    return tuple(result)


def can_say_here(state: AuctionState, actor: int) -> bool:
    return (
        state.outcome == AuctionOutcome.BIDDING
        and actor == state.turn == state.first_hand
        and state.high_bid is not None
        and state.high_bidder != actor
        and state.high_bid != Bid.regular(6, Suit.SPADES)
    )


def _next_active(
    state: AuctionState, actor: int, active: frozenset[int], holder: int | None
) -> int | None:
    for step in (1, 2, 3):
        seat = (actor + step) % 3
        if seat in active and seat != holder:
            return seat
    return None


def apply_auction_action(state: AuctionState, actor: int, action: AuctionAction) -> AuctionState:
    if state.outcome != AuctionOutcome.BIDDING or actor != state.turn or actor not in state.active:
        raise RuleViolation("Not this player's auction turn")
    if not isinstance(action, AuctionAction):
        raise RuleViolation("Invalid auction action")
    high = state.high_bid
    high_bidder = state.high_bidder
    active = state.active
    made_bid = state.made_bid
    misere_bidders = state.misere_bidders
    if action.kind == AuctionActionKind.PASS:
        if action.bid is not None:
            raise RuleViolation("Pass cannot contain a bid")
        active = active - {actor}
    elif action.kind == AuctionActionKind.HERE:
        if action.bid is not None or not can_say_here(state, actor):
            raise RuleViolation("The first hand cannot hold this bid")
        high_bidder = actor
        made_bid = made_bid | {actor}
    elif action.kind == AuctionActionKind.BID:
        if action.bid not in legal_auction_bids(state, actor):
            raise RuleViolation("Bid is not legal")
        high = action.bid
        high_bidder = actor
        made_bid = made_bid | {actor}
        if action.bid is not None and action.bid.kind == BidKind.MISERE:
            misere_bidders = misere_bidders | {actor}
    else:
        raise RuleViolation("Unknown auction action")
    history = (*state.history, AuctionEvent(actor, action))
    if high is None and not active:
        return replace(
            state, active=active, history=history, turn=None, outcome=AuctionOutcome.PASSOUT
        )
    if high is not None and active == frozenset((high_bidder,)):
        return replace(
            state,
            high_bid=high,
            high_bidder=high_bidder,
            active=active,
            made_bid=made_bid,
            misere_bidders=misere_bidders,
            history=history,
            turn=None,
            outcome=AuctionOutcome.WON,
        )
    turn = _next_active(state, actor, active, high_bidder)
    if turn is None:
        raise AssertionError("Auction is active without an eligible bidder")
    return replace(
        state,
        high_bid=high,
        high_bidder=high_bidder,
        active=active,
        made_bid=made_bid,
        misere_bidders=misere_bidders,
        history=history,
        turn=turn,
    )


def legal_final_contracts(winning_bid: Bid) -> tuple[Bid, ...]:
    """Final suit may rise, but a different bid class cannot be selected."""
    if winning_bid.kind == BidKind.REGULAR:
        return tuple(
            bid
            for bid in BID_ORDER
            if bid.kind == BidKind.REGULAR and bid.ordinal >= winning_bid.ordinal
        )
    if winning_bid.kind == BidKind.TEN_NO_WIDOW:
        return tuple(
            bid
            for bid in BID_ORDER
            if bid.kind == BidKind.TEN_NO_WIDOW and bid.ordinal >= winning_bid.ordinal
        )
    return (winning_bid,)


def replay_auction(
    dealer: int, events: tuple[AuctionEvent, ...], minimum_level: int = 6
) -> AuctionState:
    state = start_auction(dealer, minimum_level)
    for event in events:
        state = apply_auction_action(state, event.actor, event.action)
    return state
