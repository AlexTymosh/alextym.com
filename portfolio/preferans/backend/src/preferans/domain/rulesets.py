"""Validated, immutable, content-addressed rules for deterministic scoring.

A snapshot is taken when a game is created. Historical deals must never read
mutable room presets or process-wide defaults after their first settlement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class Ruleset:
    """All amounts are integer points; tuples are ordered by levels 6..10."""

    identifier: str = "zaporizhzhia-classic"
    version: int = 1
    pool_target: int = 20
    regular_costs: tuple[int, int, int, int, int] = (2, 4, 6, 8, 10)
    misere_cost: int = 10
    passout_costs: tuple[int, int, int] = (1, 2, 3)
    single_vist_required: tuple[int, int, int, int, int] = (4, 2, 1, 1, 1)
    double_vist_required: tuple[int, int, int, int, int] = (4, 2, 2, 1, 1)
    double_personal_required: tuple[int, int, int] = (2, 1, 1)
    half_vist_award: int = 8
    trick_vist_multiplier: int = 2
    consolation_multiplier: int = 2
    help_vists_per_point: int = 10
    surplus_vists_per_opponent: int = 5
    hill_vist_numerator: int = 10
    hill_vist_denominator: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("Ruleset identifier must be nonempty")
        _integer(self.version, "version", 1)
        _integer(self.pool_target, "pool_target", 1)
        for key, size in (
            ("regular_costs", 5),
            ("passout_costs", 3),
            ("single_vist_required", 5),
            ("double_vist_required", 5),
            ("double_personal_required", 3),
        ):
            value = getattr(self, key)
            if type(value) is not tuple or len(value) != size:
                raise ValueError(f"{key} must be a {size}-element tuple")
            for number in value:
                _integer(number, key, 1)
        for key in (
            "misere_cost",
            "half_vist_award",
            "trick_vist_multiplier",
            "consolation_multiplier",
            "help_vists_per_point",
            "surplus_vists_per_opponent",
            "hill_vist_numerator",
            "hill_vist_denominator",
        ):
            _integer(getattr(self, key), key, 1)
        for count in self.single_vist_required + self.double_vist_required:
            if count > 10:
                raise ValueError("Defender trick requirement exceeds ten")
        if self.double_personal_required[0] * 2 != self.double_vist_required[0]:
            raise ValueError("Level 6 personal obligations must match the joint obligation")
        if self.double_personal_required[1] * 2 != self.double_vist_required[1]:
            raise ValueError("Level 7 personal obligations must match the joint obligation")
        if self.double_personal_required[2] * 2 != self.double_vist_required[2]:
            raise ValueError("Level 8 personal obligations must match the joint obligation")

    def cost(self, level: int) -> int:
        if type(level) is not int or level not in range(6, 11):
            raise ValueError("Regular contract level must be 6..10")
        return self.regular_costs[level - 6]

    def passout_cost(self, level: int) -> int:
        if type(level) is not int or level not in (6, 7, 8):
            raise ValueError("Passout level must be 6, 7 or 8")
        return self.passout_costs[level - 6]

    def fingerprint(self) -> str:
        """Stable SHA-256 over the complete numerical rules and their version."""
        data = json.dumps(asdict(self), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RulesetSnapshot:
    rules: Ruleset
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.rules, Ruleset) or self.sha256 != self.rules.fingerprint():
            raise ValueError("Ruleset fingerprint does not match the immutable snapshot")


def freeze_ruleset(rules: Ruleset) -> RulesetSnapshot:
    if not isinstance(rules, Ruleset):
        raise TypeError("Only validated Ruleset objects can be frozen")
    return RulesetSnapshot(rules, rules.fingerprint())
