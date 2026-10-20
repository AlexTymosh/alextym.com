"""Consistent pre-migration backup for the active v2 SQLite (Windows-safe)."""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "backend" / "_local" / "vor_hub.sqlite3"
DEST = ROOT / "backend" / "_local" / "vor_backups"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    source = (args.source or Path(os.getenv("VOR_DEMO_DB_PATH") or DEFAULT)).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Active v2 SQLite not found: {source}")
    DEST.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = DEST / f"v2-before-pr02-{stamp}.sqlite3"
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=20)) as live:
        with closing(sqlite3.connect(target)) as backup:
            live.backup(backup)
            result = backup.execute("PRAGMA integrity_check").fetchone()[0]
            count = backup.execute("SELECT count(*) FROM vehicles").fetchone()[0]
    if result != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError(f"SQLite backup integrity check failed: {result}")
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"Verified pre-migration backup: {target}")
    print(f"Vehicles: {count} | SHA-256: {checksum}")
    print("Original SQLite remains unchanged. Keep this private backup outside Git.")


if __name__ == "__main__":
    main()
