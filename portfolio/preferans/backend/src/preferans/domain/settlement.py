"""Exact zero-sum reconciliation and pairwise post-game consequences.

These operations are read-only projections over a closed financial ledger. A
sheet discard is a different terminal outcome and is handled separately.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ledger import ScoreState


@dataclass(frozen=True, slots=True)
class PairPunishment:
    winner: int
    loser: int
    difference: int
    ordinary_units: int
    bare: int
    ordinary: int


def _round_nearest_positive(numerator: int, denominator: int) -> int:
    """Half-up for nonnegative rational numbers without floats."""
    if type(numerator) is not int or numerator < 0:
        raise ValueError("Numerator must be a nonnegative integer")
    if type(denominator) is not int or denominator < 1:
        raise ValueError("Denominator must be positive")
    return (2 * numerator + denominator) // (2 * denominator)


def final_hill_vists(state: ScoreState) -> tuple[int, int, int]:
    rules = state.ruleset.rules
    return tuple(
        _round_nearest_positive(h * rules.hill_vist_numerator, rules.hill_vist_denominator)
        for h in state.hill
    )


def net_results(state: ScoreState) -> tuple[int, int, int]:
    """R_i = sum_j (W_ij - W_ji + G_j - G_i)."""
    hills = final_hill_vists(state)
    balances = tuple(
        sum(state.vists[i][j] - state.vists[j][i] + hills[j] - hills[i] for j in range(3) if i != j)
        for i in range(3)
    )
    if sum(balances) != 0:
        raise AssertionError("Pairwise ledger violated its zero-sum invariant")
    return balances


def placements(results: tuple[int, int, int]) -> tuple[int | None, int | None, int | None]:
    """Competition ranks; a triple tie awards no places or gold medals."""
    if len(results) != 3 or any(type(x) is not int for x in results):
        raise ValueError("Exactly three integer net results required")
    if len(set(results)) == 1:
        return None, None, None
    return tuple(1 + sum(other > score for other in results) for score in results)


def pair_punishments(
    results: tuple[int, int, int], *, prefer_bare: bool = True
) -> tuple[PairPunishment, ...]:
    """One ordinary unit per started 50, per unordered pair.

    prefer_bare is only a display-default proposal; the eventual loser may
    elect ten ordinary units in place of each bare punch in PR 7.
    """
    placements(results)  # Validate the triple, including all-tied values.
    awards = []
    for i in range(3):
        for j in range(i + 1, 3):
            difference = abs(results[i] - results[j])
            if difference == 0:
                continue
            winner, loser = (i, j) if results[i] > results[j] else (j, i)
            units = (difference + 49) // 50
            bare, ordinary = divmod(units, 10) if prefer_bare else (0, units)
            awards.append(PairPunishment(winner, loser, difference, units, bare, ordinary))
    return tuple(awards)


def discard_sheet_penalties(loser: int) -> tuple[PairPunishment, ...]:
    """Voluntary accepted sheet discard: one bare from each opponent, no math."""
    if type(loser) is not int or loser not in range(3):
        raise ValueError("Invalid sheet-discard loser")
    return tuple(PairPunishment(i, loser, 0, 10, 1, 0) for i in range(3) if i != loser)


def discard_sheet_placements(loser: int) -> tuple[int, int, int]:
    if type(loser) is not int or loser not in range(3):
        raise ValueError("Invalid sheet-discard loser")
    return tuple(3 if i == loser else 1 for i in range(3))
