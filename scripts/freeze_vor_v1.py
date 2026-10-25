"""PR-01: freeze the existing Fleet VOR demo into an isolated v1.

Run once from the repository root AFTER taking/checking a backup of the desired
source environment. A consistent SQLite backup preserves uncheckpointed WAL data.
No live SQLite file, passwords, or real contact details enter Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "app"
DEFAULT_SOURCE = BACKEND / "_local" / "vor_hub.sqlite3"
DEFAULT_V1 = BACKEND / "_local" / "vor_hub_01.sqlite3"
DEFAULT_BACKUPS = BACKEND / "_local" / "vor_backups"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def assert_database(db: sqlite3.Connection) -> dict[str, int]:
    integrity = db.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
    # A database already used by the demo must have these core tables.
    names = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not row[0].startswith("sqlite_")
    }
    mandatory = {"vehicles", "tickets", "events", "ticket_steps", "contacts", "subscriptions"}
    if mandatory - names:
        raise RuntimeError(f"Source is not an existing Fleet VOR database; missing: {sorted(mandatory - names)}")
    broken = db.execute("PRAGMA foreign_key_check").fetchall()
    if broken:
        raise RuntimeError(f"SQLite foreign_key_check found {len(broken)} broken references")
    return {
        name: db.execute('SELECT COUNT(*) FROM "' + name.replace('\"', '\"\"') + '"').fetchone()[0]
        for name in sorted(names)
    }


def open_source(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(
            f"Running SQLite database was not found: {path}\n"
            "Supply --source with the REAL existing file. Do not substitute a seed database.\n"
            "If your current data is on a remote host, first obtain a consistent SQLite backup there."
        )
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=20)


def backup_to(source: sqlite3.Connection, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite: {destination}")
    # A temporary file in the same directory is renamed only after validation.
    handle, temp_path = tempfile.mkstemp(prefix=".vor-copy-", suffix=".sqlite3", dir=destination.parent)
    os.close(handle)
    temp = Path(temp_path)
    try:
        with closing(sqlite3.connect(temp)) as copied:
            source.backup(copied, pages=100, sleep=0.05)
            assert_database(copied)
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)


def ensure_count_match(expected: dict[str, int], path: Path) -> None:
    with sqlite3.connect(path) as target:
        actual = assert_database(target)
    if actual != expected:
        raise AssertionError(f"SQLite table counts differ from snapshot: {path}")


def change_exact(content: str, old: str, new: str, file: str) -> str:
    occurrences = content.count(old)
    if occurrences != 1:
        raise RuntimeError(f"Unsafe upstream change in {file}: expected 1 occurrence, got {occurrences}: {old[:90]!r}")
    return content.replace(old, new, 1)


def prepare_code() -> dict[Path, str]:
    old_ui = FRONTEND / "fleet-vor-hub"
    frozen_ui = FRONTEND / "fleet-vor-hub-01"
    old_api = BACKEND / "app" / "api" / "vor.py"
    old_store = BACKEND / "app" / "services" / "vor_store.py"
    old_export = BACKEND / "app" / "services" / "vor_exports.py"
    old_main = BACKEND / "app" / "main.py"
    paths = [old_ui / "VorHub.tsx", old_ui / "vor.module.css", old_ui / "page.tsx", old_api, old_store, old_export, old_main]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Required source file missing: {path}")

    ui = (old_ui / "VorHub.tsx").read_text(encoding="utf-8")
    ui = change_exact(ui, 'const API = "/api/vor";', 'const API = "/api/vor-01";', "VorHub.tsx")

    store = old_store.read_text(encoding="utf-8")
    store = change_exact(
        store,
        'LOCAL_FILE = Path(__file__).resolve().parents[2] / "_local" / "vor_hub.sqlite3"',
        'LOCAL_FILE = Path(__file__).resolve().parents[2] / "_local" / "vor_hub_01.sqlite3"',
        "vor_store.py",
    )
    store = change_exact(store, 'os.getenv("VOR_DEMO_DB_PATH", "")', 'os.getenv("VOR_V1_DB_PATH", "")', "vor_store.py")
    store = change_exact(
        store,
        '    return Path(raw).expanduser().resolve() if raw else LOCAL_FILE',
        '    frozen_path = Path(raw).expanduser().resolve() if raw else LOCAL_FILE\n'
        '    active_raw = os.getenv("VOR_DEMO_DB_PATH", "").strip()\n'
        '    active_path = (Path(active_raw).expanduser().resolve() if active_raw else\n'
        '                   Path(__file__).resolve().parents[2] / "_local" / "vor_hub.sqlite3")\n'
        '    if frozen_path == active_path:\n'
        '        raise RuntimeError("v1 and v2 cannot share the same SQLite database")\n'
        '    return frozen_path',
        "vor_store.py",
    )
    store = change_exact(
        store,
        '    if not path.exists():\n        shutil.copy2(SEED_FILE, path)',
        '    if not path.is_file():\n        raise FileNotFoundError(f"Frozen v1 SQLite is missing: {path}; run scripts/freeze_vor_v1.py")',
        "vor_store.py",
    )
    # Remove ALL first-use mutation/seed/migrations from the frozen reader.
    begin = '    db.executescript("""\n      CREATE TABLE IF NOT EXISTS maintenance_bookings ('
    finish = '    try:\n        yield db'
    if store.count(begin) != 1 or store.count(finish) != 1:
        raise RuntimeError("Frozen v1 store bootstrap markers differ; refusing to guess at migrations")
    i = store.index(begin)
    j = store.index(finish, i)
    store = store[:i] + (
        '    # The frozen database is a full snapshot. Do not apply new schema migrations,\n'
        '    # initialise bookings, or change subscriber assignments on read.\n'
    ) + store[j:]
    store = store.replace('import shutil\n', '', 1)
    store = store.replace('SEED_FILE = Path(__file__).with_name("vor_seed.sqlite3")\n', '', 1)

    api = old_api.read_text(encoding="utf-8")
    for x,y in [
        ('from app.services import vor_store', 'from app.services import vor_store_v1 as vor_store'),
        ('from app.services.vor_exports import build_xlsx, build_ics', 'from app.services.vor_exports_v1 import build_xlsx, build_ics'),
        ('APIRouter(prefix="/vor",', 'APIRouter(prefix="/vor-01",'),
        ('COOKIE = "vor_demo_session"', 'COOKIE = "vor_01_demo_session"'),
        ('"alextym-vor-demo:v1:"', '"alextym-vor-demo:archived-v1:"'),
        ('os.getenv("VOR_DEMO_SEND_REAL_EMAIL",', 'os.getenv("VOR_V1_SEND_REAL_EMAIL",'),
        ('path="/api/vor"', 'path="/api/vor-01"'),
    ]:
        hits = api.count(x)
        if hits < 1:
            raise RuntimeError(f"API marker not found: {x}")
        api = api.replace(x, y)
    api = api.replace(
        'os.getenv("VOR_DEMO_PASSWORD", "")',
        '(os.getenv("VOR_V1_PASSWORD") or os.getenv("VOR_DEMO_PASSWORD", ""))',
    )
    # Existing password continues to work; VOR_V1_PASSWORD optionally isolates v1 credentials.
    # v1 real email is independently disabled until explicitly enabled.
    if '"VOR_DEMO_SEND_REAL_EMAIL"' in api:
        raise RuntimeError("Frozen API still uses v2 live-email flag")

    main = old_main.read_text(encoding="utf-8")
    marker = 'from app.api.vor import router as vor_router\n'
    if 'from app.api.vor_v1 import router as vor_v1_router' not in main:
        main = change_exact(main, marker, marker + 'from app.api.vor_v1 import router as vor_v1_router\n', "main.py")
    marker = '    app.include_router(vor_router, prefix="/api")\n'
    if 'app.include_router(vor_v1_router, prefix="/api")' not in main:
        main = change_exact(main, marker, marker + '    app.include_router(vor_v1_router, prefix="/api")\n', "main.py")
    page = (old_ui / "page.tsx").read_text(encoding="utf-8")
    return {
        frozen_ui / "VorHub.tsx": ui,
        frozen_ui / "vor.module.css": (old_ui / "vor.module.css").read_text(encoding="utf-8"),
        frozen_ui / "page.tsx": page,
        BACKEND / "app" / "api" / "vor_v1.py": api,
        BACKEND / "app" / "services" / "vor_store_v1.py": store,
        BACKEND / "app" / "services" / "vor_exports_v1.py": old_export.read_text(encoding="utf-8"),
        old_main: main,
    }


def write_code(code: dict[Path, str]) -> None:
    main = BACKEND / "app" / "main.py"
    # Never rewrite a previously frozen version from a potentially modified v2.
    frozen = [p for p in code if p != main]
    existing = [p for p in frozen if p.exists()]
    if existing:
        raise FileExistsError(
            "v1 source freeze already exists; refusing to regenerate frozen code: "
            + ", ".join(str(p.relative_to(ROOT)) for p in existing)
        )
    for path in frozen:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code[path], encoding="utf-8", newline="\n")
    main.write_text(code[main], encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None, help="Existing ACTIVE v2 SQLite database")
    parser.add_argument("--v1-target", type=Path, default=None, help="Destination for frozen v1 SQLite")
    parser.add_argument("--backups-dir", type=Path, default=DEFAULT_BACKUPS, help="Private retained backups")
    parser.add_argument("--no-code", action="store_true", help="Snapshot only (unit tests / recovery)")
    args = parser.parse_args(argv)
    source = (args.source or Path(os.getenv("VOR_DEMO_DB_PATH", "") or DEFAULT_SOURCE)).expanduser().resolve()
    target = (args.v1_target or Path(os.getenv("VOR_V1_DB_PATH", "") or DEFAULT_V1)).expanduser().resolve()
    backup_dir = args.backups_dir.expanduser().resolve()
    if source == target:
        raise ValueError("Refusing to share a database between versions")
    if target.is_file():
        raise FileExistsError(f"v1 database already exists; will not overwrite: {target}")
    if not args.no_code:
        code = prepare_code()  # preflight before data snapshot
        if any(p.exists() for p in code if p != BACKEND / "app" / "main.py"):
            raise FileExistsError("Frozen v1 code already exists. Refusing to overwrite your v1 baseline.")
    # Don't hide a missing/remote original DB by copying the built-in seed file.
    with closing(open_source(source)) as db:
        original_counts = assert_database(db)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"v1-source-{timestamp}.sqlite3"
        if backup.exists():
            raise FileExistsError(f"A backup with this timestamp already exists: {backup}")
        backup_to(db, backup)
    ensure_count_match(original_counts, backup)
    # The v1 database is cloned from the verified backup, not a new seed.
    with closing(open_source(backup)) as db:
        backup_to(db, target)
    ensure_count_match(original_counts, target)
    if sha256(backup) != sha256(target):
        raise AssertionError("Backup and frozen v1 bytes differ")
    manifest = {
        "timestamp_utc": timestamp,
        "source": str(source),
        "v1_target": str(target),
        "backup": str(backup),
        "sha256_backup": sha256(backup),
        "sha256_v1": sha256(target),
        "table_row_counts": original_counts,
        "note": "Local/private snapshot. Original SQLite remains the v2 database. Do not commit this manifest or either DB.",
    }
    manifest_path = backup_dir / f"v1-source-{timestamp}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not args.no_code:
        write_code(code)
    print(f"Frozen v1 SQLite: {target}")
    print(f"Private verified backup: {backup}")
    print(f"Private checksum/counts manifest: {manifest_path}")
    print(f"Snapshot tables: {len(original_counts)}; primary records: {original_counts.get('vehicles', 0)} vehicles, {original_counts.get('events', 0)} events")
    print("v1 and v2 now have distinct database paths; verify with pytest and browser before G0 approval")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, FileNotFoundError, FileExistsError, AssertionError, sqlite3.Error) as exc:
        print(f"Freeze aborted: {exc}", file=sys.stderr)
        sys.exit(1)
