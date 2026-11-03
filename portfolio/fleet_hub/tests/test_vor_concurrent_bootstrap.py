"""Concurrency contracts for the Fleet SQLite schema bootstrap.

Every database in this module lives under pytest tmp_path. No test opens the
packaged seed for writing or the persistent _local Fleet database.
"""

from __future__ import annotations

import multiprocessing
import os
import sqlite3

import pytest

from fleet_hub.persistence.schema import bootstrap_lock, ensure_schema
from fleet_hub.services import vor_data, vor_operations as ops, vor_store


def _worker_open_database(path: str, start, results) -> None:
    """Top-level worker for multiprocessing spawn on Windows and POSIX."""
    try:
        if not start.wait(timeout=15):
            raise TimeoutError("Worker start gate was not released")
        os.environ["VOR_DEMO_DB_PATH"] = path
        with vor_data.database() as db:
            ops._setup(db)
            vehicles = db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
            actions = db.execute("SELECT COUNT(*) FROM ops_stage_settings").fetchone()[0]
            results.put(("ok", vehicles, actions))
    except BaseException as exc:
        results.put(("error", type(exc).__name__, str(exc)))
        raise


def _two_workers(path) -> list[tuple]:
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    results = ctx.Queue()
    workers = [
        ctx.Process(target=_worker_open_database, args=(str(path), start, results))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    start.set()
    try:
        for worker in workers:
            worker.join(timeout=35)
        assert all(not worker.is_alive() for worker in workers), "Fleet bootstrap workers hung"
        assert [worker.exitcode for worker in workers] == [0, 0]
        return [results.get(timeout=5) for _ in workers]
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=5)
        results.close()
        results.join_thread()


def test_two_processes_bootstrap_fresh_seed_once_safely(tmp_path) -> None:
    path = tmp_path / "concurrent-fresh.sqlite3"
    assert _two_workers(path) == [("ok", 20, 18), ("ok", 20, 18)]
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20
        assert (
            db.execute(
                "SELECT COUNT(*) FROM vor_status_events WHERE event_kind='baseline'"
            ).fetchone()[0]
            == 20
        )
        assert db.execute("SELECT COUNT(*) FROM vor_schema_versions").fetchone()[0] >= 3


def test_two_processes_recover_missing_ops_schema_and_keep_manual_data(
    monkeypatch, tmp_path
) -> None:
    path = tmp_path / "concurrent-recovery.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_data.database() as db:
        ops._setup(db)
        db.execute("UPDATE vehicles SET garage='Manually assigned' WHERE id=1")
        db.execute("DROP TABLE ops_audit")
        db.commit()

    results = _two_workers(path)
    assert results == [("ok", 20, 18), ("ok", 20, 18)]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0] == (
            "Manually assigned"
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ops_audit'"
        ).fetchone()


def test_schema_guard_skips_initialized_database_without_sidecar(tmp_path) -> None:
    path = tmp_path / "already-ready.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE ready (id INTEGER PRIMARY KEY)")
        db.commit()
        ensure_schema(
            db,
            lambda conn: (
                conn.execute("SELECT 1 FROM sqlite_master WHERE name='ready'").fetchone()
                is not None
            ),
            lambda _: pytest.fail("Ready schema must not be migrated"),
        )
    assert not path.with_name(f".{path.name}.bootstrap.lock").exists()


def test_schema_lock_is_released_after_initializer_error(tmp_path) -> None:
    path = tmp_path / "failure.sqlite3"
    with sqlite3.connect(path) as db:
        with pytest.raises(RuntimeError, match="expected failure"):
            ensure_schema(
                db,
                lambda _: False,
                lambda _: (_ for _ in ()).throw(RuntimeError("expected failure")),
            )
        # A second attempt must reacquire the lock and initialize successfully.
        ensure_schema(
            db,
            lambda conn: (
                conn.execute("SELECT 1 FROM sqlite_master WHERE name='repaired'").fetchone()
                is not None
            ),
            lambda conn: conn.execute("CREATE TABLE repaired (id INTEGER PRIMARY KEY)"),
        )
        assert db.execute("SELECT name FROM sqlite_master WHERE name='repaired'").fetchone()


def test_seed_copy_failure_never_publishes_partial_database(monkeypatch, tmp_path) -> None:
    path = tmp_path / "incomplete.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))

    def fail_halfway(_source, destination):
        destination = os.fspath(destination)
        with open(destination, "wb") as dest:
            dest.write(b"partial copy")
        raise RuntimeError("synthetic interrupted copy")

    with monkeypatch.context() as patch:
        patch.setattr(vor_store.shutil, "copy2", fail_halfway)
        with pytest.raises(RuntimeError, match="interrupted copy"):
            with vor_store.connection():
                pass
    assert not path.exists()
    assert not list(tmp_path.glob(".incomplete.sqlite3.seed-*.tmp"))
    with vor_store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20


def test_lock_is_not_held_during_business_operations(monkeypatch, tmp_path) -> None:
    path = tmp_path / "working.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    with vor_store.connection() as db:
        # This call would time out if the store kept its bootstrap lock through yield.
        with bootstrap_lock(path, timeout=0.2):
            assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20
