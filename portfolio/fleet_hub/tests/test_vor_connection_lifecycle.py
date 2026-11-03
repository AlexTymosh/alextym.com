"""Characterize Fleet SQLite lifecycle using disposable, isolated database files.

Never point these tests at the runtime _local database or the packaged seed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fleet_hub.persistence import sqlite as sqlite_persistence
from fleet_hub.services import vor_store


class TrackingConnection(sqlite3.Connection):
    def close(self) -> None:
        self.was_closed = True
        super().close()


def _track_connections(monkeypatch: pytest.MonkeyPatch) -> list[TrackingConnection]:
    original_connect = sqlite3.connect
    connections: list[TrackingConnection] = []

    def tracking_connect(*args, **kwargs):
        conn = original_connect(*args, factory=TrackingConnection, **kwargs)
        conn.was_closed = False
        connections.append(conn)
        return conn

    monkeypatch.setattr(sqlite_persistence.sqlite3, "connect", tracking_connect)
    return connections


def test_connection_bootstraps_fresh_database_and_closes(monkeypatch, tmp_path):
    active = tmp_path / "new" / "fleet.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(active))
    tracked = _track_connections(monkeypatch)

    with vor_store.connection() as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 15000
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20
        assert db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0] > 0

    assert active.is_file()
    assert len(tracked) == 1 and tracked[0].was_closed is True


def test_second_open_does_not_erase_manual_edits(monkeypatch, tmp_path):
    active = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(active))
    with vor_store.connection() as db:
        db.execute("UPDATE vehicles SET garage=? WHERE id=1", ("Manual workshop",))
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0]

    with vor_store.connection() as db:
        garage = db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0]
        assert garage == "Manual workshop"
        assert db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0] == count
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_bootstrap_failure_still_closes_connection(monkeypatch, tmp_path):
    active = tmp_path / "broken-bootstrap.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(active))
    tracked = _track_connections(monkeypatch)

    def broken_migration(db):
        raise RuntimeError("synthetic migration failure")

    monkeypatch.setattr(vor_store, "migrate_v1_demo", broken_migration)
    with pytest.raises(RuntimeError, match="synthetic migration failure"):
        with vor_store.connection():
            pass

    assert len(tracked) == 1 and tracked[0].was_closed is True


def test_low_level_context_rolls_back_uncommitted_changes_on_error(tmp_path):
    path = Path(tmp_path) / "rollback.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE records (value TEXT NOT NULL)")

    with pytest.raises(RuntimeError, match="synthetic operation failure"):
        with sqlite_persistence.open_sqlite(path) as db:
            db.execute("INSERT INTO records(value) VALUES ('should-not-persist')")
            raise RuntimeError("synthetic operation failure")

    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
