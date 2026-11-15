"""Seed, reset, and version semantics for a shared Workforce demo dataset."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from uuid import uuid4

from workforce_intelligence.database import Database, DatabaseUnavailable
from workforce_intelligence.migrations import SOURCE_TABLES

RESET_COOLDOWN_SECONDS = 15


class Conflict(Exception):
    pass


class InvalidOperation(Exception):
    pass


class RecordNotFound(Exception):
    pass


class ResetThrottled(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


@dataclass(frozen=True)
class DatasetVersion:
    dataset_id: str
    dataset_generation: int


@dataclass(frozen=True)
class DatasetState(DatasetVersion):
    revision: int
    scenario_code: str
    generation_seed: int
    seed_version: str
    history_start: str
    as_of_date: str
    generated_at: str
    refreshed_at: str


@dataclass(frozen=True)
class SeedDefinition:
    scenario_code: str
    generation_seed: int
    seed_version: str
    history_start: date
    as_of_date: date
    populate: Callable[[sqlite3.Connection, int], None]


@dataclass(frozen=True)
class AuditActor:
    uid: str
    correlation_id: str
    channel: str = "api"


@dataclass(frozen=True)
class ResetResult:
    dataset: DatasetState
    reset_generation: int
    replayed: bool


def _read_state(connection: sqlite3.Connection) -> DatasetState | None:
    row = connection.execute("""
        SELECT dataset_id, dataset_generation, revision, scenario_code, generation_seed,
               seed_version, history_start, as_of_date, generated_at, refreshed_at
        FROM dataset_state WHERE singleton = 1
    """).fetchone()
    return DatasetState(**dict(row)) if row else None


def current_dataset(
    connection: sqlite3.Connection, expected: DatasetVersion | None = None
) -> DatasetState:
    state = _read_state(connection)
    if state is None:
        raise DatabaseUnavailable("Workforce dataset has not been seeded")
    if expected and (state.dataset_id, state.dataset_generation) != (
        expected.dataset_id,
        expected.dataset_generation,
    ):
        raise Conflict("The demo dataset changed. Refresh and retry.")
    return state


def ensure_dataset(database: Database, seed: SeedDefinition) -> DatasetState:
    with database.transaction() as connection:
        if state := _read_state(connection):
            return state
    with database.transaction(write=True) as connection:
        # A different process may already have installed the seed while we waited.
        return _read_state(connection) or _install_seed(connection, seed, str(uuid4()), 1)


def _install_seed(
    connection: sqlite3.Connection,
    seed: SeedDefinition,
    dataset_id: str,
    generation: int,
) -> DatasetState:
    now = datetime.now(UTC).isoformat()
    state = DatasetState(
        dataset_id=dataset_id,
        dataset_generation=generation,
        revision=0,
        scenario_code=seed.scenario_code,
        generation_seed=seed.generation_seed,
        seed_version=seed.seed_version,
        history_start=seed.history_start.isoformat(),
        as_of_date=seed.as_of_date.isoformat(),
        generated_at=now,
        refreshed_at=now,
    )
    connection.execute("DELETE FROM dataset_state")
    connection.execute(
        """
        INSERT INTO dataset_state (singleton, dataset_id, dataset_generation, revision, scenario_code,
            generation_seed, seed_version, history_start, as_of_date, generated_at, refreshed_at)
        VALUES (1, :dataset_id, :dataset_generation, :revision, :scenario_code, :generation_seed,
            :seed_version, :history_start, :as_of_date, :generated_at, :refreshed_at)
        """,
        asdict(state),
    )
    seed.populate(connection, seed.generation_seed)
    return state


def reset_dataset(
    database: Database,
    seed: SeedDefinition,
    *,
    expected: DatasetVersion,
    actor: AuditActor,
    idempotency_key: str,
) -> ResetResult:
    with database.transaction(write=True) as connection:
        state = current_dataset(connection)
        if expected.dataset_id != state.dataset_id:
            raise Conflict("The demo dataset changed. Refresh and retry.")
        receipt = connection.execute(
            "SELECT prior_generation, reset_generation FROM reset_receipts "
            "WHERE actor_uid = ? AND idempotency_key = ?",
            (actor.uid, idempotency_key),
        ).fetchone()
        if receipt:
            if expected.dataset_generation != receipt["prior_generation"]:
                raise Conflict("The reset key was used with a different dataset version.")
            return ResetResult(state, receipt["reset_generation"], replayed=True)

        current_dataset(connection, expected)
        if state.dataset_generation > 1:
            elapsed = (
                datetime.now(UTC) - datetime.fromisoformat(state.generated_at)
            ).total_seconds()
            if elapsed < RESET_COOLDOWN_SECONDS:
                raise ResetThrottled(math.ceil(RESET_COOLDOWN_SECONDS - elapsed))

        for table in reversed(SOURCE_TABLES):
            connection.execute(f"DELETE FROM {table}")
        connection.execute("DELETE FROM audit_events")
        replacement = _install_seed(
            connection, seed, state.dataset_id, state.dataset_generation + 1
        )
        connection.execute(
            "INSERT INTO reset_receipts VALUES (?, ?, ?, ?)",
            (
                actor.uid,
                idempotency_key,
                state.dataset_generation,
                replacement.dataset_generation,
            ),
        )
        record_audit(
            connection,
            replacement,
            actor,
            entity_type="dataset",
            entity_key=state.dataset_id,
            action="reset",
            old_values={
                "generation": state.dataset_generation,
                "revision": state.revision,
            },
            new_values={"generation": replacement.dataset_generation, "revision": 0},
        )
        return ResetResult(replacement, replacement.dataset_generation, replayed=False)


def advance_revision(connection: sqlite3.Connection, state: DatasetState) -> DatasetState:
    updated = replace(
        state, revision=state.revision + 1, refreshed_at=datetime.now(UTC).isoformat()
    )
    connection.execute(
        "UPDATE dataset_state SET revision = ?, refreshed_at = ? WHERE singleton = 1",
        (updated.revision, updated.refreshed_at),
    )
    return updated


def operation_date(state: DatasetState, effective_date: date) -> str:
    value = effective_date.isoformat()
    if not state.history_start <= value <= state.as_of_date:
        raise InvalidOperation("Choose a date within the demo dataset's observed period.")
    return value


def record_audit(
    connection: sqlite3.Connection,
    state: DatasetState,
    actor: AuditActor,
    *,
    entity_type: str,
    entity_key: str,
    action: str,
    old_values: dict | None,
    new_values: dict,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events (entity_type, entity_key, action, occurred_at, actor_uid,
            old_values, new_values, source_channel, correlation_id, demo_session_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            entity_key,
            action,
            state.refreshed_at,
            actor.uid,
            json.dumps(old_values) if old_values is not None else None,
            json.dumps(new_values),
            actor.channel,
            actor.correlation_id,
            f"{state.dataset_id}:{state.dataset_generation}",
        ),
    )
