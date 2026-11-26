"""Consensual award of the remaining tricks; never fabricate card play."""

from dataclasses import replace

from .auction import RuleViolation
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


def offer_claim(game: GameState, seat: int) -> GameState:
    if not can_claim(game, seat):
        raise RuleViolation("Remaining tricks cannot be offered now")
    return replace(game, claim=TrickClaim(seat, len(game.completed_tricks), game.trick))


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
    counts = list(game.tricks_won)
    counts[claim.seat] += 10 - len(game.completed_tricks)
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
