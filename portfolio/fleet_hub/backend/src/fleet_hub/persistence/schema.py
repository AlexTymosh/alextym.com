"""Read-only SQLite schema probes for Fleet bootstrap decisions.

Never mutate the connection or cache readiness across SQLite database files.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection


def has_schema_objects(db: sqlite3.Connection, required: Collection[str]) -> bool:
    """Check table/index names on the current connection without executing DDL."""
    existing = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'index')")
    }
    return set(required).issubset(existing)
