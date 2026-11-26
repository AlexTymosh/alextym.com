"""Immutable deal-level state machine. No HTTP, storage, wall clock or I/O.

IMPORTANT: GameState contains private hands, widow and discard. It MUST NEVER be
returned directly to a browser or published as a shared Firestore document.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .auction import (
    AuctionAction,
    AuctionOutcome,
    AuctionState,
    Bid,
    BidKind,
    RuleViolation,
    apply_auction_action,
    legal_final_contracts,
    start_auction,
)
from .cards import Card, Deal, Suit
from .play import CompletedTrick, PlayedCard, legal_cards, winning_card


class Phase(str, Enum):
    AUCTION = "auction"
    DISCARD = "discard"
    DECLARE = "declare"
    MISERE_OFFER = "misere_offer"
    DEFENSE_FIRST = "defense_first"
    DEFENSE_SECOND = "defense_second"
    DEFENSE_RECONSIDER = "defense_reconsider"
    CHOOSE_MODE = "choose_mode"
    OPENING_LEAD = "opening_lead"
    PLAY = "play"
    FINISHED = "finished"


class DefenseDecision(str, Enum):
    VIST = "vist"
    PASS = "pass"
    HALF = "half"


class DefenseMode(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class EndReason(str, Enum):
    PLAYED = "played"
    ALL_PASSED = "all_passed"
    HALF_VIST = "half_vist"
    WITHOUT_THREE = "without_three"
    MISERE_ACCEPTED = "misere_accepted"
    ALL_MINE_ACCEPTED = "all_mine_accepted"


@dataclass(frozen=True, slots=True)
class TrickClaim:
    seat: int
    at_tricks: int
    partial: tuple[PlayedCard, ...] = ()
    approved: frozenset[int] = frozenset()
    rejected_by: int | None = None
    accepted: bool = False


@dataclass(frozen=True, slots=True)
class GameState:
    # PRIVILEGED SERVER-ONLY state: includes all hidden cards and private actions.
    dealer: int
    first_hand: int
    passout_level: int
    hands: tuple[tuple[Card, ...], tuple[Card, ...], tuple[Card, ...]]
    widow: tuple[Card, Card]
    auction: AuctionState
    phase: Phase = Phase.AUCTION
    turn: int | None = None
    declarer: int | None = None
    winning_bid: Bid | None = None
    contract: Bid | None = None
    discarded: tuple[Card, ...] = ()
    widow_revealed: int = 0
    defense: tuple[DefenseDecision | None, DefenseDecision | None, DefenseDecision | None] = (
        None,
        None,
        None,
    )
    mode: DefenseMode | None = None
    controllers: tuple[int, int, int] = (0, 1, 2)
    exposed_hands: frozenset[int] = frozenset()
    trick: tuple[PlayedCard, ...] = ()
    completed_tricks: tuple[CompletedTrick, ...] = ()
    tricks_won: tuple[int, int, int] = (0, 0, 0)
    end_reason: EndReason | None = None
    half_vist_receiver: int | None = None
    misere_votes: frozenset[int] = frozenset()
    misere_resume_turn: int | None = None
    misere_refused_at: int | None = None
    claim: TrickClaim | None = None

    @property
    def claim_pending(self) -> bool:
        return self.claim is not None and not self.claim.accepted and self.claim.rejected_by is None

    @property
    def is_passout(self) -> bool:
        return self.auction.outcome == AuctionOutcome.PASSOUT

    @property
    def is_misere(self) -> bool:
        return self.contract is not None and self.contract.kind in (
            BidKind.MISERE,
            BidKind.MISERE_NO_WIDOW,
        )


def start_game(cards: Deal, passout_level: int = 6) -> GameState:
    if not isinstance(cards, Deal):
        raise ValueError("Expected an authoritative Deal")
    if cards.first_hand != (cards.dealer + 1) % 3:
        raise ValueError("Inconsistent first hand")
    if sorted(len(hand) for hand in cards.hands) != [10, 10, 10]:
        raise ValueError("Every player must receive ten cards")
    all_cards = (*cards.hands[0], *cards.hands[1], *cards.hands[2], *cards.widow)
    if len(all_cards) != 32 or len(set(all_cards)) != 32:
        raise ValueError("Duplicate or missing cards")
    auction = start_auction(cards.dealer, passout_level)
    return GameState(
        cards.dealer,
        cards.first_hand,
        passout_level,
        cards.hands,
        cards.widow,
        auction,
        turn=auction.turn,
    )


def auction_action(state: GameState, actor: int, action: AuctionAction) -> GameState:
    if state.phase != Phase.AUCTION:
        raise RuleViolation("Auction is closed")
    auction = apply_auction_action(state.auction, actor, action)
    if auction.outcome == AuctionOutcome.BIDDING:
        return replace(state, auction=auction, turn=auction.turn)
    if auction.outcome == AuctionOutcome.PASSOUT:
        return replace(
            state,
            auction=auction,
            phase=Phase.PLAY,
            turn=state.first_hand,
            widow_revealed=1,
        )
    assert auction.high_bidder is not None and auction.high_bid is not None
    bid = auction.high_bid
    return replace(
        state,
        auction=auction,
        phase=Phase.DISCARD if bid.uses_widow else Phase.DECLARE,
        turn=auction.high_bidder,
        declarer=auction.high_bidder,
        winning_bid=bid,
        widow_revealed=2 if bid.uses_widow else 0,
    )


def discard_cards(state: GameState, actor: int, discarded: tuple[Card, Card]) -> GameState:
    if state.phase != Phase.DISCARD or actor != state.declarer:
        raise RuleViolation("Only the declarer may discard after winning the widow")
    if len(discarded) != 2 or discarded[0] == discarded[1]:
        raise RuleViolation("Discard exactly two distinct cards")
    hand = (*state.hands[actor], *state.widow)
    if not all(card in hand for card in discarded):
        raise RuleViolation("Card is not in the declarer's twelve-card hand")
    remaining = tuple(card for card in hand if card not in discarded)
    if len(remaining) != 10:
        raise AssertionError("Invalid discard result")
    hands = tuple(remaining if seat == actor else state.hands[seat] for seat in range(3))
    return replace(state, hands=hands, discarded=discarded, phase=Phase.DECLARE)


def declare_contract(state: GameState, actor: int, contract: Bid) -> GameState:
    if state.phase != Phase.DECLARE or actor != state.declarer:
        raise RuleViolation("Not the declarer's contract announcement turn")
    if state.winning_bid is None or contract not in legal_final_contracts(state.winning_bid):
        raise RuleViolation("Final contract is below the auction minimum or changes bid class")
    state = replace(state, contract=contract)
    if state.is_misere:
        defenders = frozenset(seat for seat in range(3) if seat != actor)
        return replace(
            state,
            phase=Phase.PLAY,
            turn=state.first_hand,
            exposed_hands=defenders if state.first_hand != actor else frozenset(),
        )
    if contract == Bid.regular(6, Suit.SPADES):
        defense = list(state.defense)
        for seat in range(3):
            if seat != actor:
                defense[seat] = DefenseDecision.VIST
        return replace(
            state,
            defense=tuple(defense),
            phase=Phase.PLAY,
            turn=state.first_hand,
        )
    return replace(state, phase=Phase.DEFENSE_FIRST, turn=(actor + 1) % 3)


def can_offer_misere(state: GameState, actor: int) -> bool:
    if type(actor) is not int or actor not in range(3) or state.declarer is None:
        return False
    if state.claim_pending or state.tricks_won[state.declarer] or state.winning_bid is None:
        return False
    if state.winning_bid.kind not in (BidKind.MISERE, BidKind.MISERE_NO_WIDOW):
        return False
    if len(state.discarded) != (2 if state.winning_bid.uses_widow else 0):
        return False
    if state.misere_refused_at is not None and state.misere_refused_at >= len(
        state.completed_tricks
    ):
        return False
    if state.phase == Phase.DECLARE:
        return (
            actor == state.declarer
            and state.contract is None
            and not state.trick
            and not state.completed_tricks
            and len(state.hands[actor]) == 10
        )
    return (
        state.phase == Phase.PLAY
        and state.is_misere
        and state.turn is not None
        and len(state.completed_tricks) < 10
    )


def offer_misere(state: GameState, actor: int) -> GameState:
    """Declarer offers success; a defender's offer is their own approval."""
    if not can_offer_misere(state, actor):
        raise RuleViolation("Misere success cannot be offered now")
    defenders = frozenset(range(3)) - {state.declarer}
    votes = frozenset({actor}) if actor in defenders else frozenset()
    return replace(
        state,
        contract=state.winning_bid,
        phase=Phase.MISERE_OFFER,
        turn=next(
            i for i in ((state.declarer + 1) % 3, (state.declarer + 2) % 3) if i not in votes
        ),
        misere_votes=votes,
        misere_resume_turn=state.turn if state.phase == Phase.PLAY else None,
    )


def vote_misere(state: GameState, actor: int, approve: bool) -> GameState:
    if (
        state.phase != Phase.MISERE_OFFER
        or state.declarer is None
        or type(actor) is not int
        or actor not in range(3)
        or actor == state.declarer
        or actor in state.misere_votes
        or type(approve) is not bool
    ):
        raise RuleViolation("Invalid or repeated misere vote")
    if not approve:
        if state.misere_resume_turn is not None:
            return replace(
                state,
                phase=Phase.PLAY,
                turn=state.misere_resume_turn,
                misere_votes=frozenset(),
                misere_resume_turn=None,
                misere_refused_at=len(state.completed_tricks),
            )
        # Legacy declaration-time offers have no previous play turn.
        contract = state.contract
        restored = replace(
            state,
            phase=Phase.DECLARE,
            turn=state.declarer,
            contract=None,
            misere_votes=frozenset(),
            exposed_hands=frozenset(),
            misere_refused_at=len(state.completed_tricks),
        )
        return declare_contract(restored, state.declarer, contract)
    votes = state.misere_votes | {actor}
    defenders = frozenset(range(3)) - {state.declarer}
    if votes == defenders:
        return replace(
            state,
            phase=Phase.FINISHED,
            turn=None,
            end_reason=EndReason.MISERE_ACCEPTED,
            misere_votes=votes,
            misere_resume_turn=None,
            exposed_hands=frozenset(),
            hands=((), (), ()),
            trick=(),
            claim=None,
        )
    return replace(state, misere_votes=votes, turn=next(iter(defenders - votes)))


def concede_without_three(state: GameState, actor: int, contract: Bid | None = None) -> GameState:
    """Concede the winning auction bid, without declaring another contract."""
    if state.phase != Phase.DECLARE or state.declarer != actor or state.is_passout:
        raise RuleViolation("Without-three concession is only allowed during declaration")
    winning = state.winning_bid
    if winning is None or winning.kind not in (BidKind.REGULAR, BidKind.TEN_NO_WIDOW):
        raise RuleViolation("Misere cannot be conceded without three")
    # Legacy clients may send the exact winning bid; an alternative is forbidden.
    if contract is not None and contract != winning:
        raise RuleViolation("Without-three must use the winning auction bid")
    contract = winning
    if state.trick or state.completed_tricks or any(state.defense):
        raise RuleViolation("Defense or play has already started")
    return replace(
        state,
        contract=contract,
        phase=Phase.FINISHED,
        turn=None,
        end_reason=EndReason.WITHOUT_THREE,
    )


def _defense_after_decision(state: GameState) -> GameState:
    """Once the two defender decisions are final, start mode selection or play."""
    assert state.declarer is not None
    defenders = tuple(seat for seat in range(3) if seat != state.declarer)
    visters = tuple(seat for seat in defenders if state.defense[seat] == DefenseDecision.VIST)
    if not visters:
        second_defender = (state.declarer + 2) % 3
        reason = (
            EndReason.HALF_VIST
            if state.defense[second_defender] == DefenseDecision.HALF
            else EndReason.ALL_PASSED
        )
        eligible_half = state.contract is not None and state.contract.level in (6, 7)
        return replace(
            state,
            phase=Phase.FINISHED,
            turn=None,
            end_reason=reason,
            half_vist_receiver=second_defender if eligible_half else None,
        )
    if len(visters) == 2:
        return replace(state, phase=Phase.PLAY, turn=state.first_hand)
    return replace(
        state,
        phase=Phase.OPENING_LEAD if state.first_hand == state.declarer else Phase.CHOOSE_MODE,
        turn=state.first_hand if state.first_hand == state.declarer else visters[0],
    )


def decide_defense(state: GameState, actor: int, decision: DefenseDecision) -> GameState:
    if not isinstance(decision, DefenseDecision):
        raise RuleViolation("Invalid defense action")
    if state.declarer is None or state.contract is None or state.is_misere:
        raise RuleViolation("No defender decision is required")
    first = (state.declarer + 1) % 3
    second = (state.declarer + 2) % 3
    if state.turn != actor:
        raise RuleViolation("Not this defender's turn")
    defense = list(state.defense)
    if state.phase == Phase.DEFENSE_FIRST:
        if actor != first or decision == DefenseDecision.HALF:
            raise RuleViolation("First defender may only vist or pass")
        defense[first] = decision
        return replace(state, defense=tuple(defense), phase=Phase.DEFENSE_SECOND, turn=second)
    if state.phase == Phase.DEFENSE_SECOND:
        if actor != second:
            raise RuleViolation("Not the second defender")
        if decision == DefenseDecision.HALF:
            if state.defense[first] != DefenseDecision.PASS or state.contract.level not in (6, 7):
                raise RuleViolation("Half-vist requires a first pass on level 6 or 7")
            defense[second] = decision
            return replace(
                state, defense=tuple(defense), phase=Phase.DEFENSE_RECONSIDER, turn=first
            )
        defense[second] = decision
        return _defense_after_decision(replace(state, defense=tuple(defense)))
    if state.phase == Phase.DEFENSE_RECONSIDER:
        if actor != first or decision == DefenseDecision.HALF:
            raise RuleViolation("First defender may return to vist or confirm pass")
        defense[first] = decision
        if decision == DefenseDecision.VIST:
            defense[second] = DefenseDecision.PASS
        return _defense_after_decision(replace(state, defense=tuple(defense)))
    raise RuleViolation("Defender decisions are closed")


def choose_defense_mode(state: GameState, actor: int, mode: DefenseMode) -> GameState:
    if state.claim_pending or state.phase != Phase.CHOOSE_MODE or not isinstance(mode, DefenseMode):
        raise RuleViolation("Defense mode cannot be selected now")
    visters = [seat for seat, d in enumerate(state.defense) if d == DefenseDecision.VIST]
    passers = [seat for seat, d in enumerate(state.defense) if d == DefenseDecision.PASS]
    if visters != [actor] or len(passers) != 1:
        raise RuleViolation("Only the sole visting defender may select mode")
    controllers = list(state.controllers)
    exposed = state.exposed_hands
    if mode == DefenseMode.OPEN:
        controllers[passers[0]] = actor
        exposed = exposed | {passers[0]}
    return replace(
        state,
        phase=Phase.PLAY,
        mode=mode,
        controllers=tuple(controllers),
        exposed_hands=exposed,
        turn=(state.trick[-1].owner + 1) % 3 if state.trick else state.first_hand,
    )


def legal_play_cards(state: GameState, owner: int) -> tuple[Card, ...]:
    if (
        state.claim_pending
        or state.phase not in (Phase.PLAY, Phase.OPENING_LEAD)
        or state.turn != owner
    ):
        return ()
    if state.phase == Phase.OPENING_LEAD and owner != state.declarer:
        return ()
    if state.is_passout:
        forced = (
            state.widow[len(state.completed_tricks)].suit
            if len(state.completed_tricks) < 2
            else None
        )
        trump = None
    else:
        forced = None
        trump = state.contract.suit if state.contract is not None else None
    led = state.trick[0].card.suit if state.trick else None
    return legal_cards(state.hands[owner], led, trump, forced)


def play_card(state: GameState, actor: int, card: Card, owner: int | None = None) -> GameState:
    if state.phase not in (Phase.PLAY, Phase.OPENING_LEAD) or state.turn is None:
        raise RuleViolation("Cards may not be played in this phase")
    hand_owner = state.turn if owner is None else owner
    if hand_owner != state.turn or state.controllers[hand_owner] != actor:
        raise RuleViolation("Actor does not control the hand due to play")
    if card not in legal_play_cards(state, hand_owner):
        raise RuleViolation("Card is absent or violates following suit/trump")
    hands = tuple(
        (
            tuple(c for c in state.hands[seat] if c != card)
            if seat == hand_owner
            else state.hands[seat]
        )
        for seat in range(3)
    )
    trick = (*state.trick, PlayedCard(hand_owner, actor, card))
    if len(trick) < 3:
        next_state = replace(state, hands=hands, trick=trick, turn=(hand_owner + 1) % 3)
        if state.is_misere and state.declarer == hand_owner and len(trick) == 1:
            defenders = frozenset(seat for seat in range(3) if seat != state.declarer)
            next_state = replace(next_state, exposed_hands=defenders)
        if state.phase == Phase.OPENING_LEAD:
            visters = [seat for seat, d in enumerate(state.defense) if d == DefenseDecision.VIST]
            assert len(visters) == 1
            next_state = replace(next_state, phase=Phase.CHOOSE_MODE, turn=visters[0])
        return next_state
    number = len(state.completed_tricks) + 1
    forced = state.widow[number - 1].suit if state.is_passout and number <= 2 else None
    trump = state.contract.suit if state.contract is not None else None
    winner, effective = winning_card(trick, trump, forced)
    completed = (*state.completed_tricks, CompletedTrick(number, trick, winner, effective))
    counts = list(state.tricks_won)
    counts[winner] += 1
    if number == 10:
        return replace(
            state,
            hands=hands,
            trick=(),
            completed_tricks=completed,
            tricks_won=tuple(counts),
            turn=None,
            phase=Phase.FINISHED,
            end_reason=EndReason.PLAYED,
        )
    next_lead = state.first_hand if state.is_passout and number < 3 else winner
    reveal = 2 if state.is_passout and number == 1 else state.widow_revealed
    return replace(
        state,
        hands=hands,
        trick=(),
        completed_tricks=completed,
        tricks_won=tuple(counts),
        turn=next_lead,
        widow_revealed=reveal,
    )
