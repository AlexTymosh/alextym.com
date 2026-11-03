"""Read-only SQLite schema probes for Fleet bootstrap decisions.

Never mutate the connection or cache readiness across SQLite database files.
"""

from __future__ import annotations

import errno
import os
import sqlite3
import time
from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager
from pathlib import Path


def has_schema_objects(db: sqlite3.Connection, required: Collection[str]) -> bool:
    """Check table/index names on the current connection without executing DDL."""
    existing = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'index')")
    }
    return set(required).issubset(existing)


def _main_database_path(db: sqlite3.Connection) -> Path | None:
    """Resolve the active main database; :memory: connections need no process lock."""
    for _, name, filename in db.execute("PRAGMA database_list"):
        if name == "main":
            return Path(filename) if filename else None
    return None


@contextmanager
def bootstrap_lock(path: Path, *, timeout: float = 30.0) -> Iterator[None]:
    """Serialize Fleet schema bootstrap across processes on Windows and POSIX.

    A persistent, per-database sidecar file is used for OS advisory locking.
    The operating system releases the lock when a process exits, even after a
    crash. The file itself is harmless and must not be deleted while in use.
    """
    lock_path = path.with_name(f".{path.name}.bootstrap.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        # Windows locks a byte range. Ensure byte zero exists before locking it.
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()

        if os.name == "nt":
            import msvcrt

            def acquire() -> None:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

            def release() -> None:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

        else:
            import fcntl

            def acquire() -> None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release() -> None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        deadline = time.monotonic() + timeout
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for Fleet DB bootstrap: {path}") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            release()


def ensure_schema(
    db: sqlite3.Connection,
    ready: Callable[[sqlite3.Connection], bool],
    initialize: Callable[[sqlite3.Connection], None],
) -> None:
    """Run a migration once, with a readiness recheck under the process lock.

    Existing memory-only fixtures use the same sequence without a filesystem
    lock. This does not cache readiness and never touches another database.
    """
    if ready(db):
        return
    path = _main_database_path(db)
    if path is None:
        if not ready(db):
            initialize(db)
    else:
        with bootstrap_lock(path):
            if not ready(db):
                initialize(db)
