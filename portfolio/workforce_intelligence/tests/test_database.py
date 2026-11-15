import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import date

import pytest

from workforce_intelligence import database as sqlite_store
from workforce_intelligence.contracts import change_fte
from workforce_intelligence.database import Database, DatabaseUnavailable
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    ResetThrottled,
    SeedDefinition,
    current_dataset,
    ensure_dataset,
    reset_dataset,
)

ACTOR = AuditActor("test-member", "req_data_core")


def populate(connection: sqlite3.Connection, _seed: int) -> None:
    connection.execute("INSERT INTO employees VALUES ('demo-a', 'Demo A.', 1, 1, 1)")
    connection.execute("""
        INSERT INTO employment_contracts VALUES (1, 'demo-a', 1000, 1, '2026-07-01', NULL,
            '2026-07-01T00:00:00Z', 'test-seed', 'baseline')
    """)


TEST_SEED = SeedDefinition("tests", 1, "1", date(2026, 7, 1), date(2026, 10, 31), populate)


def test_concurrent_lazy_bootstrap_preserves_single_generation(tmp_path):
    path = tmp_path / "workforce.sqlite3"
    with ThreadPoolExecutor(max_workers=4) as pool:
        states = tuple(pool.map(lambda _: ensure_dataset(Database(path), TEST_SEED), range(8)))
    assert all(state == states[0] for state in states)
    assert states[0].dataset_generation == 1
    with Database(path).transaction() as connection:
        assert [row[0] for row in connection.execute("SELECT version FROM schema_migrations")] == [
            1
        ]
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 1


def test_migration_failure_rolls_back_and_existing_data_survives(tmp_path, monkeypatch):
    database = Database(tmp_path / "workforce.sqlite3")
    initial = ensure_dataset(database, TEST_SEED)
    migrations = sqlite_store.MIGRATIONS
    monkeypatch.setattr(
        sqlite_store,
        "MIGRATIONS",
        (*migrations, ("CREATE TABLE added (id INTEGER)", "INVALID SQL")),
    )
    with pytest.raises(DatabaseUnavailable):
        ensure_dataset(database, TEST_SEED)
    monkeypatch.setattr(sqlite_store, "MIGRATIONS", migrations)
    with database.transaction() as connection:
        assert current_dataset(connection) == initial
        assert (
            connection.execute("SELECT name FROM sqlite_schema WHERE name = 'added'").fetchall()
            == []
        )


def test_other_database_is_never_initialized_or_reset(tmp_path):
    path = tmp_path / "fleet.sqlite3"
    with closing(sqlite3.connect(path)) as fleet:
        fleet.execute("CREATE TABLE vehicles (id INTEGER PRIMARY KEY)")
        fleet.execute("INSERT INTO vehicles VALUES (1)")
        fleet.commit()
    before = path.read_bytes()
    with pytest.raises(DatabaseUnavailable, match="another application"):
        ensure_dataset(Database(path), TEST_SEED)
    assert path.read_bytes() == before

    workforce = Database(tmp_path / "workforce.sqlite3")
    state = ensure_dataset(workforce, TEST_SEED)
    reset_dataset(workforce, TEST_SEED, expected=state, actor=ACTOR, idempotency_key="r1")
    assert path.read_bytes() == before


def test_schema_rejects_missing_references_and_overlapping_effective_periods(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    ensure_dataset(database, TEST_SEED)
    with database.transaction(write=True) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute("""
                INSERT INTO candidate_applications VALUES ('a', 'missing', '2026-08-01', 'test')
            """)
        with pytest.raises(sqlite3.IntegrityError, match="Effective periods overlap"):
            connection.execute("""
                INSERT INTO employment_contracts VALUES (2, 'demo-a', 800, 1, '2026-08-01', NULL,
                    '2026-08-01T00:00:00Z', 'test-seed', 'overlap')
            """)


def test_effective_fte_change_is_atomic_and_rejects_concurrent_stale_edit(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    state = ensure_dataset(database, TEST_SEED)

    def edit():
        return change_fte(
            database,
            employee_id="demo-a",
            record_version=1,
            effective_from=date(2026, 9, 1),
            fte_milli=800,
            expected=state,
            actor=ACTOR,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        edits = [pool.submit(edit), pool.submit(edit)]
    failures = [future.exception() for future in edits if future.exception() is not None]
    assert len(failures) == 1
    assert isinstance(failures[0], Conflict)
    assert "employee changed" in str(failures[0])

    with database.transaction() as connection:
        assert current_dataset(connection).revision == 1
        rows = connection.execute("""
            SELECT valid_from, valid_to, contracted_fte_milli FROM employment_contracts ORDER BY valid_from
        """).fetchall()
        assert list(map(tuple, rows)) == [
            ("2026-07-01", "2026-09-01", 1000),
            ("2026-09-01", None, 800),
        ]
        audit = connection.execute("SELECT * FROM audit_events").fetchone()
        assert audit["actor_uid"] == ACTOR.uid
        assert audit["correlation_id"] == ACTOR.correlation_id
        assert audit["demo_session_id"] == f"{state.dataset_id}:1"
        assert json.loads(audit["old_values"])["fte_milli"] == 1000
        assert json.loads(audit["new_values"])["fte_milli"] == 800


def test_reset_serializes_retries_and_invalidates_old_epoch(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    initial = ensure_dataset(database, TEST_SEED)

    def reset():
        return reset_dataset(
            database, TEST_SEED, expected=initial, actor=ACTOR, idempotency_key="r1"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda _: reset(), range(2)))
    assert sorted(result.replayed for result in results) == [False, True]
    assert {result.reset_generation for result in results} == {2}
    state = results[0].dataset
    assert state.dataset_id == initial.dataset_id
    assert state.revision == 0
    with pytest.raises(Conflict, match="dataset changed"):
        reset_dataset(database, TEST_SEED, expected=initial, actor=ACTOR, idempotency_key="r2")
    with pytest.raises(ResetThrottled) as exc:
        reset_dataset(database, TEST_SEED, expected=state, actor=ACTOR, idempotency_key="r2")
    assert exc.value.retry_after > 0
    with database.transaction() as connection:
        assert [row[0] for row in connection.execute("SELECT action FROM audit_events")] == [
            "reset"
        ]


def test_failed_reset_preserves_prior_data_and_receipts(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    initial = ensure_dataset(database, TEST_SEED)

    def bad_seed(connection, _seed):
        populate(connection, _seed)
        raise ValueError("fixture interrupted")

    with pytest.raises(ValueError, match="fixture interrupted"):
        reset_dataset(
            database,
            replace(TEST_SEED, populate=bad_seed),
            expected=initial,
            actor=ACTOR,
            idempotency_key="reset",
        )
    assert ensure_dataset(database, TEST_SEED) == initial
    with database.transaction() as connection:
        assert connection.execute("SELECT display_name FROM employees").fetchone()[0] == "Demo A."
        assert connection.execute("SELECT * FROM reset_receipts").fetchall() == []


def test_recreated_database_has_new_identity(tmp_path):
    state = ensure_dataset(Database(tmp_path / "prior.sqlite3"), TEST_SEED)
    other = Database(tmp_path / "recreated.sqlite3")
    assert ensure_dataset(other, TEST_SEED).dataset_id != state.dataset_id
    with other.transaction() as connection:
        with pytest.raises(Conflict, match="dataset changed"):
            current_dataset(connection, state)
