"""Workforce-only SQLite connections and transactional schema upgrades."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from workforce_intelligence.migrations import MIGRATIONS

DEFAULT_PATH = Path(".tmp/workforce/workforce.sqlite3")
APPLICATION_ID = 0x574F5246  # WORF


class DatabaseUnavailable(Exception):
    pass


class DatabaseBusy(Exception):
    pass


class Database:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=3, isolation_level=None)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                _migrate(connection)
                with _atomic(connection, write=write):
                    yield connection
        except OSError as exc:
            raise DatabaseUnavailable from exc
        except sqlite3.Error as exc:
            if getattr(exc, "sqlite_errorcode", 0) & 255 in (
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            ):
                raise DatabaseBusy from exc
            raise DatabaseUnavailable from exc


@contextmanager
def _atomic(connection: sqlite3.Connection, *, write: bool = False) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def _schema_version(connection: sqlite3.Connection) -> int:
    owner = connection.execute("PRAGMA application_id").fetchone()[0]
    if owner == APPLICATION_ID:
        version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        if version is not None and 1 <= version <= len(MIGRATIONS):
            return version
        raise DatabaseUnavailable("Unsupported Workforce schema version")
    if owner != 0 or connection.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone():
        raise DatabaseUnavailable("Database belongs to another application")
    return 0


def _migrate(connection: sqlite3.Connection) -> None:
    with _atomic(connection):
        if _schema_version(connection) == len(MIGRATIONS):
            return
    with _atomic(connection, write=True):
        version = _schema_version(connection)
        if version == 0:
            connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            connection.execute("""
                CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)
                STRICT
            """)
        for next_version, statements in enumerate(MIGRATIONS[version:], start=version + 1):
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations VALUES (?, ?)",
                (next_version, datetime.now(UTC).isoformat()),
            )
