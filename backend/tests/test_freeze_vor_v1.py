"""Consistent SQLite backup test, including WAL-mode writes and no overwrite."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from contextlib import closing

import pytest


def _freeze_module():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "freeze_vor_v1", root / "scripts" / "freeze_vor_v1.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_snapshot_wal_integrity_and_overwrite_guard(tmp_path):
    tool = _freeze_module()
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "private" / "backup.sqlite3"
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
        for name in ["vehicles", "tickets", "events", "ticket_steps", "contacts", "subscriptions"]:
            db.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, value TEXT)")
            db.execute(f"INSERT INTO {name} (value) VALUES (?)", ("Synthetic payload",))
        db.commit()
        counts = tool.assert_database(db)
        with closing(tool.open_source(source)) as read:
            tool.backup_to(read, backup)
        tool.ensure_count_match(counts, backup)
        assert tool.sha256(backup)
        with pytest.raises(FileExistsError):
            with closing(tool.open_source(source)) as read:
                tool.backup_to(read, backup)
        # Source was NOT replaced, even with uncheckpointed WAL content.
        assert db.execute("SELECT value FROM events").fetchone()[0] == "Synthetic payload"


def test_backup_closes_destination_before_renaming(monkeypatch, tmp_path):
    """Windows rejects os.replace while SQLite still holds the destination file."""
    tool = _freeze_module()
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "backup.sqlite3"
    with closing(sqlite3.connect(source)) as initial:
        for name in ("vehicles", "tickets", "events", "ticket_steps", "contacts", "subscriptions"):
            initial.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)")
        initial.commit()

    real_connect = sqlite3.connect
    observed = {"closed": False}

    class TrackConnection(sqlite3.Connection):
        def close(self):
            observed["closed"] = True
            super().close()

    def connect(path, *args, **kwargs):
        if Path(path).name.startswith(".vor-copy-"):
            kwargs["factory"] = TrackConnection
        return real_connect(path, *args, **kwargs)

    real_replace = Path.replace

    def replace(path, destination):
        assert observed["closed"], "SQLite handle must be closed before os.replace"
        return real_replace(path, destination)

    monkeypatch.setattr(tool.sqlite3, "connect", connect)
    monkeypatch.setattr(Path, "replace", replace)
    with closing(tool.open_source(source)) as read:
        tool.backup_to(read, target)
    assert target.exists()
    tool.ensure_count_match(
        {
            name: 0
            for name in (
                "vehicles",
                "tickets",
                "events",
                "ticket_steps",
                "contacts",
                "subscriptions",
            )
        },
        target,
    )
