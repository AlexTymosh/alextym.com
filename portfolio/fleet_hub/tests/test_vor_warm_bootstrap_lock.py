"""Regression tests for avoiding OS locks on already initialized Fleet SQLite.

All databases are isolated under tmp_path; never open the runtime DB directly.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from fleet_hub.services import vor_store


def test_warm_connection_skips_interprocess_lock(monkeypatch, tmp_path) -> None:
    path = tmp_path / "warm.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection() as db:
        db.execute("UPDATE vehicles SET garage='Owner workshop' WHERE id=1")
        db.commit()

    @contextmanager
    def forbidden_lock(_path):
        pytest.fail("Warm Fleet reads must not acquire the bootstrap lock")
        yield

    monkeypatch.setattr(vor_store, "bootstrap_lock", forbidden_lock)
    monkeypatch.setattr(
        vor_store,
        "_initialize_store_schema",
        lambda db: pytest.fail("Warm Fleet schema must not be reinitialized"),
    )
    with vor_store.connection() as db:
        assert db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0] == (
            "Owner workshop"
        )
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_incomplete_schema_rechecks_under_lock_and_repairs(monkeypatch, tmp_path) -> None:
    path = tmp_path / "repair.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection():
        pass
    with sqlite3.connect(path) as db:
        db.execute("UPDATE vehicles SET garage='Owner workshop' WHERE id=1")
        db.execute(
            "DELETE FROM vor_schema_versions WHERE name=?",
            ("v1_1_workflow_owners_20261012",),
        )
        db.commit()

    original_lock = vor_store.bootstrap_lock
    locks = []

    @contextmanager
    def traced_lock(actual_path):
        locks.append(actual_path)
        with original_lock(actual_path):
            yield

    monkeypatch.setattr(vor_store, "bootstrap_lock", traced_lock)
    with vor_store.connection() as db:
        assert (
            db.execute(
                "SELECT 1 FROM vor_schema_versions WHERE name=?",
                ("v1_1_workflow_owners_20261012",),
            ).fetchone()
            is not None
        )
        assert db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0] == (
            "Owner workshop"
        )
    assert locks == [path]


def test_second_worker_completed_migration_before_lock_recheck(monkeypatch, tmp_path) -> None:
    path = tmp_path / "recheck.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection():
        pass

    original_ready = vor_store._legacy_store_schema_ready
    probes = []

    def readiness(db):
        probes.append(True)
        if len(probes) == 1:
            return False
        return original_ready(db)

    monkeypatch.setattr(vor_store, "_legacy_store_schema_ready", readiness)
    monkeypatch.setattr(
        vor_store,
        "_initialize_store_schema",
        lambda db: pytest.fail("Other worker already completed the migration"),
    )
    with vor_store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20
    assert len(probes) == 2


def test_new_database_still_runs_first_bootstrap_and_uses_lock(monkeypatch, tmp_path) -> None:
    path = tmp_path / "new.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    original_lock = vor_store.bootstrap_lock
    original_init = vor_store._initialize_store_schema
    seen = []

    @contextmanager
    def traced_lock(actual_path):
        seen.append("lock")
        with original_lock(actual_path):
            yield

    def traced_init(db):
        seen.append("bootstrap")
        return original_init(db)

    monkeypatch.setattr(vor_store, "bootstrap_lock", traced_lock)
    monkeypatch.setattr(vor_store, "_initialize_store_schema", traced_init)
    with vor_store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20
    assert seen == ["lock", "bootstrap"]
