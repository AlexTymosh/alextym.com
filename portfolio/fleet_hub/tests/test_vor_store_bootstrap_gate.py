"""Contract tests for repeat-safe Fleet v1 schema bootstrap.

Uses disposable SQLite databases, never the runtime database or seed in place.
"""

from __future__ import annotations

import sqlite3

import pytest

from fleet_hub.persistence import sqlite as sqlite_persistence
from fleet_hub.services import vor_store


def test_warm_connection_skips_v1_schema_bootstrap(monkeypatch, tmp_path) -> None:
    path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))

    with vor_store.connection() as db:
        db.execute("UPDATE vehicles SET garage=? WHERE id=1", ("Owner workshop",))
        db.commit()

    def should_not_bootstrap(db):
        pytest.fail("Existing completed v1 schema should not reinitialize")

    monkeypatch.setattr(vor_store, "_initialize_store_schema", should_not_bootstrap)
    with vor_store.connection() as db:
        assert (
            db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0] == "Owner workshop"
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_warm_connection_does_not_execute_schema_writes(monkeypatch, tmp_path) -> None:
    path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection():
        pass

    statements: list[str] = []
    original_connect = sqlite_persistence.sqlite3.connect

    def traced_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(sqlite_persistence.sqlite3, "connect", traced_connect)
    with vor_store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20

    forbidden = ("CREATE ", "ALTER ", "DROP ", "INSERT ", "UPDATE ", "DELETE ")
    assert not [
        statement for statement in statements if statement.lstrip().upper().startswith(forbidden)
    ]


def test_missing_version_restarts_v1_bootstrap(monkeypatch, tmp_path) -> None:
    path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection():
        pass

    with sqlite3.connect(path) as db:
        db.execute(
            "DELETE FROM vor_schema_versions WHERE name=?", ("v1_1_workflow_owners_20261012",)
        )
        db.commit()

    with vor_store.connection() as db:
        assert (
            db.execute(
                "SELECT 1 FROM vor_schema_versions WHERE name=?",
                ("v1_1_workflow_owners_20261012",),
            ).fetchone()
            is not None
        )
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_missing_bookings_table_triggers_recovery(monkeypatch, tmp_path) -> None:
    path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection():
        pass

    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE maintenance_bookings")
        db.commit()

    with vor_store.connection() as db:
        # The previous initializer recreates the table but does not refill it
        # while the one-time booking initialization marker still exists.
        assert db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0] == 0
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_empty_bookings_without_initialization_marker_reseed(monkeypatch, tmp_path) -> None:
    path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection():
        pass

    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM maintenance_bookings")
        db.execute("DROP TABLE vor_bookings_initialized")
        db.commit()

    with vor_store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0] > 0
        assert db.execute("SELECT 1 FROM vor_bookings_initialized").fetchone() is not None


def test_new_seed_performs_full_bootstrap_even_if_seed_metadata_is_ready(
    monkeypatch, tmp_path
) -> None:
    """A freshly copied seed must follow the established migration call contract."""
    path = tmp_path / "fresh-ready-seed.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    calls = []
    original = vor_store._initialize_store_schema

    # The packaged seed may already carry all version markers. That must not
    # bypass the first-open bootstrap (or its failure/close guarantees).
    monkeypatch.setattr(vor_store, "_legacy_store_schema_ready", lambda db: True)

    def tracked_bootstrap(db):
        calls.append("initialized")
        return original(db)

    monkeypatch.setattr(vor_store, "_initialize_store_schema", tracked_bootstrap)
    with vor_store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20

    assert calls == ["initialized"]
