"""Low-level SQLite connection lifecycle for the embedded Fleet Hub.

This module only opens/configures/closes a connection. Schema migrations and
seed handling deliberately remain separate until their contracts are fully
characterized. It must not depend on Fleet services or HTTP routers.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def open_sqlite(path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a configured SQLite connection and close it even on bootstrap errors.

    The caller owns transaction commits/rollbacks; exiting this context never
    commits implicitly. The database path must already exist at call time.
    """
    db = sqlite3.connect(path, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        yield db
    finally:
        db.close()
