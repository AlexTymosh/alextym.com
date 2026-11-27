"""Consensual award of the remaining tricks; never fabricate card play."""

from dataclasses import replace

from .auction import BidKind, RuleViolation
from .cards import Card, Suit
from .game import DefenseDecision, EndReason, GameState, Phase, TrickClaim

PLAY_PHASES = (Phase.PLAY, Phase.OPENING_LEAD, Phase.CHOOSE_MODE)


def claim_voters(game: GameState, seat: int) -> frozenset[int]:
    others = frozenset(range(3)) - {seat}
    if game.is_passout or game.is_misere or game.defense[seat] == DefenseDecision.PASS:
        return others
    return frozenset(
        i for i in others if i == game.declarer or game.defense[i] == DefenseDecision.VIST
    )


def can_claim(game: GameState, seat: int) -> bool:
    return (
        type(seat) is int
        and seat in range(3)
        and game.phase in PLAY_PHASES
        and (game.is_passout or game.contract is not None)
        and bool(game.hands[seat] or any(p.owner == seat for p in game.trick))
        and len(game.completed_tricks) < 10
        and not game.claim_pending
        and (game.claim is None or game.claim.at_tricks < len(game.completed_tricks))
        and bool(claim_voters(game, seat))
    )


BY_OWN_TARGETS = {6: (4,), 7: (2, 3), 8: (1, 2), 9: (1,)}


def sole_vister(game: GameState, seat: int) -> int | None:
    contract = game.contract
    if (
        type(seat) is not int
        or seat != game.declarer
        or game.is_passout
        or contract is None
        or contract.kind != BidKind.REGULAR
        or contract.level not in BY_OWN_TARGETS
        or (contract.level == 6 and contract.suit == Suit.SPADES)
    ):
        return None
    defenders = [i for i in range(3) if i != seat]
    visters = [i for i in defenders if game.defense[i] == DefenseDecision.VIST]
    passers = [i for i in defenders if game.defense[i] == DefenseDecision.PASS]
    return visters[0] if len(visters) == len(passers) == 1 else None


def claim_awards(game: GameState, seat: int, target: int | None) -> tuple[int, int, int]:
    """Allocate only the remaining tricks, preserving all actual winners."""
    remaining = 10 - len(game.completed_tricks)
    if type(seat) is not int or seat not in range(3) or not 1 <= remaining <= 10:
        raise RuleViolation("Invalid remaining tricks")
    awards = [0, 0, 0]
    if target is None:
        awards[seat] = remaining
    else:
        defender = sole_vister(game, seat)
        if (
            defender is None
            or type(target) is not int
            or target not in BY_OWN_TARGETS[game.contract.level]
        ):
            raise RuleViolation("Invalid defender target")
        actual = sum(trick.winner == defender for trick in game.completed_tricks)
        needed = target - actual
        if not 0 <= needed <= remaining:
            raise RuleViolation("Defender target cannot be reached")
        # A settlement called 'by own' must still fulfill the declared contract.
        declarer_actual = sum(trick.winner == seat for trick in game.completed_tricks)
        if declarer_actual + remaining - needed < game.contract.level:
            raise RuleViolation("Declarer target cannot be reached")
        awards[defender] = needed
        awards[seat] = remaining - needed
    return tuple(awards)


def by_own_options(game: GameState, seat: int) -> tuple[int, ...]:
    if not can_claim(game, seat) or sole_vister(game, seat) is None:
        return ()
    options = []
    for target in BY_OWN_TARGETS[game.contract.level]:
        try:
            claim_awards(game, seat, target)
        except RuleViolation:
            continue
        options.append(target)
    return tuple(options)


def offer_claim(
    game: GameState,
    seat: int,
    display_order: tuple[Card, ...] | None = None,
    *,
    defender_target: int | None = None,
) -> GameState:
    if not can_claim(game, seat):
        raise RuleViolation("Remaining tricks cannot be offered now")
    if defender_target is not None and (
        type(defender_target) is not int
        or defender_target not in by_own_options(game, seat)
        or display_order is not None
    ):
        raise RuleViolation("Invalid by-own offer")
    hand = game.hands[seat]
    if display_order is not None and (
        len(display_order) != len(hand) or set(display_order) != set(hand)
    ):
        raise RuleViolation("Claim display order must match the authenticated hand")
    return replace(
        game,
        claim=TrickClaim(
            seat,
            len(game.completed_tricks),
            game.trick,
            display_order=()
            if defender_target is not None
            else hand
            if display_order is None
            else display_order,
            defender_target=defender_target,
        ),
    )


def vote_claim(game: GameState, seat: int, approve: bool) -> GameState:
    claim = game.claim
    if (
        not game.claim_pending
        or claim is None
        or type(seat) is not int
        or type(approve) is not bool
        or seat not in claim_voters(game, claim.seat)
        or seat in claim.approved
    ):
        raise RuleViolation("Invalid or repeated remaining-tricks vote")
    if not approve:
        return replace(game, claim=replace(claim, rejected_by=seat))
    updated = replace(claim, approved=claim.approved | {seat})
    if updated.approved != claim_voters(game, claim.seat):
        return replace(game, claim=updated)
    awards = claim_awards(game, claim.seat, claim.defender_target)
    counts = tuple(count + award for count, award in zip(game.tricks_won, awards))
    return replace(
        game,
        claim=replace(updated, accepted=True),
        hands=((), (), ()),
        trick=(),
        exposed_hands=frozenset(),
        tricks_won=tuple(counts),
        phase=Phase.FINISHED,
        turn=None,
        end_reason=EndReason.ALL_MINE_ACCEPTED,
    )
