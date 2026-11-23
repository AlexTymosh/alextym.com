"""Immutable directed wist ledger, hill/pool balances and exact settlement.

There is deliberately no database, clock, player UID or hidden card in this module.
All events are numeric and attributed to an explicit deal id for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .auction import RuleViolation
from .rulesets import Ruleset, RulesetSnapshot, freeze_ruleset


class EntryKind(str, Enum):
    POOL = "pool"
    HILL = "hill"
    HILL_PAYMENT = "hill_payment"
    VIST = "vist"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    sequence: int
    deal_id: str
    kind: EntryKind
    actor: int
    amount: int
    reason: str
    against: int | None = None

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("Sequence must start at 1")
        if (
            not isinstance(self.deal_id, str)
            or not self.deal_id.strip()
            or not isinstance(self.reason, str)
            or not self.reason.strip()
        ):
            raise ValueError("Ledger events require a deal ID and reason")
        if not isinstance(self.kind, EntryKind):
            raise ValueError("Unknown ledger event type")
        if type(self.actor) is not int or self.actor not in range(3):
            raise ValueError("Invalid ledger actor")
        if type(self.amount) is not int or self.amount < 1:
            raise ValueError("Ledger entry amount must be a positive integer")
        if self.kind == EntryKind.VIST:
            if type(self.against) is not int or self.against not in range(3):
                raise ValueError("Vist requires a valid debtor")
            if self.actor == self.against:
                raise ValueError("Self-directed vist is forbidden")
        elif self.against is not None:
            raise ValueError("Only vists have a debtor")


def _zero_vists() -> tuple[tuple[int, int, int], ...]:
    return ((0, 0, 0), (0, 0, 0), (0, 0, 0))


@dataclass(frozen=True, slots=True)
class ScoreState:
    ruleset: RulesetSnapshot = field(default_factory=lambda: freeze_ruleset(Ruleset()))
    pool: tuple[int, int, int] = (0, 0, 0)
    hill: tuple[int, int, int] = (0, 0, 0)
    vists: tuple[tuple[int, int, int], ...] = field(default_factory=_zero_vists)
    entries: tuple[LedgerEntry, ...] = ()
    deal_ids: tuple[str, ...] = ()
    passout_level: int = 6
    closed: bool = False
    version: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.ruleset, RulesetSnapshot):
            raise ValueError("A frozen ruleset snapshot is required")
        if self.passout_level not in (6, 7, 8) or type(self.passout_level) is not int:
            raise ValueError("Invalid passout level")
        if len(self.pool) != 3 or len(self.hill) != 3 or len(self.vists) != 3:
            raise ValueError("Exactly three players are required")
        if any(
            type(v) is not int or not 0 <= v <= self.ruleset.rules.pool_target for v in self.pool
        ):
            raise ValueError("Pool must contain whole values within its limit")
        if any(type(v) is not int or v < 0 for v in self.hill):
            raise ValueError("Hill cannot be negative")
        for row in self.vists:
            if len(row) != 3 or any(type(v) is not int or v < 0 for v in row):
                raise ValueError("Invalid directed vist matrix")
        if any(self.vists[i][i] for i in range(3)):
            raise ValueError("Self-directed vists are forbidden")
        if type(self.version) is not int or self.version < 0:
            raise ValueError("Version must be a nonnegative integer")
        if type(self.closed) is not bool or self.closed != all(
            p == self.ruleset.rules.pool_target for p in self.pool
        ):
            raise ValueError("Closed state must match the three pool balances")
        if len(self.deal_ids) != len(set(self.deal_ids)) or self.version != len(self.deal_ids):
            raise ValueError("Every deal must have one distinct settlement version")
        if any(
            not isinstance(entry, LedgerEntry) or entry.sequence != index
            for index, entry in enumerate(self.entries, 1)
        ):
            raise ValueError("Ledger event sequence must be continuous")

    @classmethod
    def new(cls, rules: Ruleset | None = None) -> ScoreState:
        return cls(ruleset=freeze_ruleset(Ruleset() if rules is None else rules))

    @property
    def target(self) -> int:
        return self.ruleset.rules.pool_target


class _Posting:
    """Private transaction buffer; never exposed or persisted until commit."""

    def __init__(self, state: ScoreState, deal_id: str):
        self.pool = list(state.pool)
        self.hill = list(state.hill)
        self.vists = [list(row) for row in state.vists]
        self.entries = list(state.entries)
        self.deal_id = deal_id
        self.rules = state.ruleset.rules

    def _record(
        self, kind: EntryKind, actor: int, amount: int, reason: str, against: int | None = None
    ) -> None:
        if type(actor) is not int or actor not in range(3) or type(amount) is not int or amount < 0:
            raise RuleViolation("Invalid numeric posting")
        if not amount:
            return
        self.entries.append(
            LedgerEntry(len(self.entries) + 1, self.deal_id, kind, actor, amount, reason, against)
        )

    def add_hill(self, seat: int, amount: int, reason: str) -> None:
        self._record(EntryKind.HILL, seat, amount, reason)
        self.hill[seat] += amount

    def pay_hill(self, seat: int, amount: int, reason: str) -> None:
        if amount > self.hill[seat]:
            raise RuleViolation("Cannot pay more hill than exists")
        self._record(EntryKind.HILL_PAYMENT, seat, amount, reason)
        self.hill[seat] -= amount

    def add_pool(self, seat: int, amount: int, reason: str) -> None:
        if self.pool[seat] + amount > self.rules.pool_target:
            raise RuleViolation("Pool target cannot be exceeded")
        self._record(EntryKind.POOL, seat, amount, reason)
        self.pool[seat] += amount

    def add_vist(self, owner: int, against: int, amount: int, reason: str) -> None:
        if owner == against or type(against) is not int or against not in range(3):
            raise RuleViolation("A vist must be directed to another seat")
        self._record(EntryKind.VIST, owner, amount, reason, against)
        self.vists[owner][against] += amount

    def finish(self, previous: ScoreState, passout_level: int) -> ScoreState:
        return ScoreState(
            ruleset=previous.ruleset,
            pool=tuple(self.pool),
            hill=tuple(self.hill),
            vists=tuple(tuple(row) for row in self.vists),
            entries=tuple(self.entries),
            deal_ids=(*previous.deal_ids, self.deal_id),
            passout_level=passout_level,
            closed=all(point == self.rules.pool_target for point in self.pool),
            version=previous.version + 1,
        )
