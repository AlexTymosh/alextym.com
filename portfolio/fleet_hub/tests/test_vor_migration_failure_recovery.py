"""Failure/retry contracts for legacy Fleet migration versions.

Tests operate exclusively on disposable tmp_path databases. The packaged seed
is copied through the existing store bootstrap; it is never opened for writing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fleet_hub.persistence import migrations
from fleet_hub.persistence.sqlite import open_sqlite
from fleet_hub.services import vor_store


@pytest.fixture
def prepared_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "migration-fault-injection.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection() as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    return path


def _tables_snapshot(db: sqlite3.Connection) -> dict[str, tuple[str, ...]]:
    """Capture stable row values, independent of SQLite result order."""
    tables = ("vehicles", "tickets", "events", "contacts", "subscriptions", "ticket_steps")
    return {
        table: tuple(sorted(repr(tuple(row)) for row in db.execute(f"SELECT * FROM {table}")))
        for table in tables
    }


def _invoke_migration(db: sqlite3.Connection, version: str) -> None:
    if version == "v1_ui_refresh_20261012":
        migrations.migrate_v1_demo(db)
    elif version == "v1_1_workflow_owners_20261012":
        migrations.migrate_v1_1_demo(db, responsible_names=vor_store.RESPONSIBLE_NAMES)
    elif version == "v1_2_subscribers_overdue_20261012":
        migrations.migrate_v1_2_demo(db)
    else:
        raise AssertionError(f"Unexpected version: {version}")


@pytest.mark.parametrize(
    ("version", "trigger_sql"),
    [
        (
            "v1_ui_refresh_20261012",
            """CREATE TEMP TRIGGER injected_migration_failure
            BEFORE INSERT ON subscriptions
            BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END""",
        ),
        (
            "v1_1_workflow_owners_20261012",
            """CREATE TEMP TRIGGER injected_migration_failure
            BEFORE UPDATE OF responsible ON vehicles WHEN NEW.id = 2
            BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END""",
        ),
        (
            "v1_2_subscribers_overdue_20261012",
            """CREATE TEMP TRIGGER injected_migration_failure
            BEFORE INSERT ON subscriptions
            BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END""",
        ),
    ],
)
def test_failed_migration_rolls_back_and_can_retry_on_same_connection(
    prepared_db: Path, version: str, trigger_sql: str
) -> None:
    with open_sqlite(prepared_db) as db:
        # Simulate an interrupted deployment with one version marker missing.
        # Preserve all other completed versions and all manual database edits.
        db.execute("DELETE FROM vor_schema_versions WHERE name=?", (version,))
        db.execute("UPDATE vehicles SET garage=? WHERE id=1", ("Owner workshop",))
        db.commit()
        before = _tables_snapshot(db)
        db.execute(trigger_sql)

        with pytest.raises(sqlite3.IntegrityError, match="injected migration failure"):
            _invoke_migration(db, version)

        # A caller that catches the exception must not inherit uncommitted
        # partial writes or disabled foreign-key enforcement on this connection.
        assert not db.in_transaction
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert _tables_snapshot(db) == before
        assert (
            db.execute("SELECT 1 FROM vor_schema_versions WHERE name=?", (version,)).fetchone()
            is None
        )

        db.execute("DROP TRIGGER injected_migration_failure")
        _invoke_migration(db, version)

        assert not db.in_transaction
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert (
            db.execute("SELECT 1 FROM vor_schema_versions WHERE name=?", (version,)).fetchone()
            is not None
        )
        assert db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0] == (
            "Owner workshop"
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    # The repaired version marker must still be present on an independent open.
    with open_sqlite(prepared_db) as db:
        assert (
            db.execute("SELECT 1 FROM vor_schema_versions WHERE name=?", (version,)).fetchone()
            is not None
        )
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
