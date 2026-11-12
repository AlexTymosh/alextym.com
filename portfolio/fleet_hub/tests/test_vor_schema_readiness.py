"""Regression contracts for read-only Fleet SQLite schema readiness gates.

Use temporary databases exclusively; never point at the persistent runtime DB.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from fleet_hub.persistence.schema import has_schema_objects
from fleet_hub.services import vor_data, vor_operations as ops, vor_store


def test_schema_probe_is_read_only_and_file_scoped(tmp_path) -> None:
    first = tmp_path / "first.sqlite3"
    second = tmp_path / "second.sqlite3"
    with sqlite3.connect(first) as db:
        db.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY)")
        db.execute("CREATE INDEX idx_marker ON marker(id)")
        assert has_schema_objects(db, {"marker", "idx_marker"})
        assert not has_schema_objects(db, {"marker", "missing"})
    with sqlite3.connect(second) as db:
        assert not has_schema_objects(db, {"marker"})
        assert db.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] == 0


def test_v2_ready_skips_schema_migration_and_ddl(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "fleet.sqlite3"))
    with vor_data.database() as db:
        assert vor_data._v2_schema_ready(db)

    original_connection = vor_store.connection
    observed: list[str] = []

    @contextmanager
    def traced_connection():
        with original_connection() as db:
            db.set_trace_callback(observed.append)
            try:
                yield db
            finally:
                db.set_trace_callback(None)

    monkeypatch.setattr(vor_store, "connection", traced_connection)
    monkeypatch.setattr(
        vor_data,
        "_migrate",
        lambda db: pytest.fail("v2 migration must not run when schema is ready"),
    )
    assert len(vor_data.register_list()["vehicles"]) == 20
    assert not any("CREATE " in statement.upper() for statement in observed)
    assert not any("ALTER TABLE" in statement.upper() for statement in observed)


def test_v2_repairs_missing_legacy_backfill_without_overwriting_user_data(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "fleet.sqlite3"))
    with vor_data.database() as db:
        row = db.execute("SELECT legacy_ticket_id FROM vor_cases LIMIT 1").fetchone()
        assert row is not None
        ticket_id = row[0]
        db.execute("DELETE FROM vor_cases WHERE legacy_ticket_id=?", (ticket_id,))
        db.execute("DELETE FROM vor_status_events WHERE vehicle_id=1 AND event_kind='baseline'")
        db.execute("UPDATE vehicles SET garage='Custom workshop' WHERE id=1")
        db.commit()
        assert not vor_data._v2_schema_ready(db)

    with vor_data.database() as db:
        assert vor_data._v2_schema_ready(db)
        assert db.execute(
            "SELECT 1 FROM vor_cases WHERE legacy_ticket_id=?", (ticket_id,)
        ).fetchone()
        assert db.execute(
            "SELECT 1 FROM vor_status_events WHERE vehicle_id=1 AND event_kind='baseline'"
        ).fetchone()
        assert db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0] == (
            "Custom workshop"
        )


def test_v2_schema_readiness_is_per_database_not_process_cache(monkeypatch, tmp_path) -> None:
    first = tmp_path / "first.sqlite3"
    second = tmp_path / "second.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(first))
    with vor_data.database() as db:
        assert vor_data._v2_schema_ready(db)
        db.execute("UPDATE vehicles SET garage='First only' WHERE id=1")
        db.commit()

    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(second))
    with vor_data.database() as db:
        assert vor_data._v2_schema_ready(db)
        assert db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0] != ("First only")


def test_ops_ready_skip_and_restore_missing_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "fleet.sqlite3"))
    with vor_data.database() as db:
        ops._setup(db)
        assert ops._ops_schema_ready(db)
        statements: list[str] = []
        db.set_trace_callback(statements.append)
        try:
            ops._setup(db)
        finally:
            db.set_trace_callback(None)
        assert not any("CREATE " in statement.upper() for statement in statements)
        assert not any("INSERT" in statement.upper() for statement in statements)

        db.execute(
            """UPDATE ops_stage_settings SET label='Custom acknowledgement', required=0
            WHERE stage_index=0 AND item_key='response_received'"""
        )
        db.execute(
            "DELETE FROM ops_stage_settings WHERE stage_index=0 AND item_key='notification_sent'"
        )
        db.commit()
        assert not ops._ops_schema_ready(db)
        ops._setup(db)
        assert ops._ops_schema_ready(db)
        restored = db.execute(
            """SELECT label FROM ops_stage_settings
            WHERE stage_index=0 AND item_key='notification_sent'"""
        ).fetchone()
        assert restored and restored[0] == "Details sent to service company"
        custom = db.execute(
            """SELECT label,required FROM ops_stage_settings
            WHERE stage_index=0 AND item_key='response_received'"""
        ).fetchone()
        assert tuple(custom) == ("Custom acknowledgement", 0)


def test_ops_recovers_missing_schema_object(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "fleet.sqlite3"))
    with vor_data.database() as db:
        ops._setup(db)
        db.execute("DROP TABLE ops_audit")
        db.commit()
        assert not ops._ops_schema_ready(db)
        ops._setup(db)
        assert ops._ops_schema_ready(db)
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ops_audit'"
        ).fetchone()
