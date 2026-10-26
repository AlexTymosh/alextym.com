"""Fleet VOR v2 data foundation. Uses only the live v2 SQLite connection.

No HOTH / KEY2 integration and no automatic change to VOR status.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

from app.services import vor_store

MAX_FILE_BYTES = 2_000_000
MAX_ROWS = 2_000
MAX_XML_BYTES = 12_000_000
COLUMNS = ("registration", "model", "garage")
HEADER_ALIASES = {
    "registration": {
        "registration",
        "reg",
        "vehicle registration",
        "registration number",
        "vrm",
        "number plate",
        "vehicle reg",
    },
    "model": {"model", "vehicle model", "make model", "vehicle type"},
    "garage": {"garage", "workshop", "depot", "base", "location"},
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalise_reg(registration: str) -> str:
    compact = re.sub(r"\s+", "", registration).upper()
    if not re.fullmatch(r"[A-Z0-9]{2,12}", compact):
        raise ValueError("Registration must be 2–12 letters/digits")
    return compact[:-3] + " " + compact[-3:] if len(compact) > 3 else compact


def normalise_header(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", str(label).strip().lower()))


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    with vor_store.connection() as db:
        # Contextmanager above closes connection, not automatically committing.
        _migrate(db)
        yield db


def _migrate(db: sqlite3.Connection) -> None:
    """Idempotent, additive migration of v2 only; no destructive ALTER/DROP."""
    db.executescript("""
      CREATE TABLE IF NOT EXISTS vor_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        legacy_ticket_id TEXT UNIQUE,
        pathway TEXT NOT NULL CHECK(pathway IN ('standard', 'tyres', 'windscreen')),
        description TEXT NOT NULL,
        vor_reason TEXT NOT NULL DEFAULT 'Unknown / Under Investigation',
        source TEXT NOT NULL DEFAULT 'demo',
        hoth_reference TEXT,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        status TEXT NOT NULL CHECK(status IN ('open','closed')),
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_vor_cases_vehicle ON vor_cases(vehicle_id,opened_at);
      CREATE TABLE IF NOT EXISTS vor_status_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        old_status TEXT,
        new_status TEXT NOT NULL,
        event_kind TEXT NOT NULL CHECK(event_kind IN ('baseline','manual')),
        actor TEXT NOT NULL,
        source TEXT NOT NULL,
        reason TEXT,
        external_reference TEXT,
        effective_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL
      );
      CREATE UNIQUE INDEX IF NOT EXISTS idx_vor_status_baseline
        ON vor_status_events(vehicle_id) WHERE event_kind='baseline';
      CREATE INDEX IF NOT EXISTS idx_vor_status_vehicle_time
        ON vor_status_events(vehicle_id,recorded_at,id);
      CREATE TABLE IF NOT EXISTS vor_import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        digest TEXT NOT NULL,
        mode TEXT NOT NULL CHECK(mode IN ('skip','update')),
        filename TEXT NOT NULL,
        created_at TEXT NOT NULL,
        row_count INTEGER NOT NULL,
        inserted_count INTEGER NOT NULL,
        updated_count INTEGER NOT NULL,
        skipped_count INTEGER NOT NULL,
        UNIQUE(digest,mode)
      );
      CREATE TABLE IF NOT EXISTS vor_import_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL REFERENCES vor_import_batches(id),
        vehicle_id INTEGER REFERENCES vehicles(id),
        registration TEXT NOT NULL,
        action TEXT NOT NULL,
        before_json TEXT,
        after_json TEXT,
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_vor_import_audit_vehicle ON vor_import_audit(vehicle_id);
      CREATE TABLE IF NOT EXISTS vor_asset_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        action TEXT NOT NULL,
        actor TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_vor_asset_events_vehicle ON vor_asset_events(vehicle_id,created_at);
    """)
    cols = {c[1] for c in db.execute("PRAGMA table_info(vehicles)")}
    if "is_archived" not in cols:
        db.execute("ALTER TABLE vehicles ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0")
    now = utcnow()
    # Preserve all legacy tickets as independent historical cases. This never edits old tickets.
    db.execute(
        """INSERT OR IGNORE INTO vor_cases
        (vehicle_id,legacy_ticket_id,pathway,description,source,hoth_reference,
         opened_at,closed_at,status,created_at)
        SELECT t.vehicle_id,t.id,
          CASE WHEN lower(t.scenario)='tyre' THEN 'tyres'
               WHEN lower(t.scenario)='glass' THEN 'windscreen' ELSE 'standard' END,
          COALESCE(NULLIF(t.title,''),'Legacy defect'),
          'legacy',t.hoth_reference,t.opened_at,
          NULL,
          CASE WHEN lower(t.status)='closed' THEN 'closed' ELSE 'open' END,?
        FROM tickets t""",
        (now,),
    )
    db.execute(
        """INSERT OR IGNORE INTO vor_status_events
      (vehicle_id,old_status,new_status,event_kind,actor,source,effective_at,recorded_at)
      SELECT v.id,NULL,v.availability_status,'baseline','Fleet Hub','initial snapshot',?,?
        FROM vehicles v""",
        (now, now),
    )
    db.commit()


def _status_baseline(db: sqlite3.Connection, vehicle_id: int, status: str) -> None:
    now = utcnow()
    db.execute(
        """INSERT OR IGNORE INTO vor_status_events
      (vehicle_id,old_status,new_status,event_kind,actor,source,effective_at,recorded_at)
      VALUES (?,NULL,?,'baseline','Fleet Hub','vehicle registration',?,?)""",
        (vehicle_id, status, now, now),
    )


def _add_vehicle(db: sqlite3.Connection, registration: str, model: str, garage: str) -> int:
    """Complete the existing v1 vehicle shape without generating a fake defect case."""
    future = (date.today() + timedelta(days=365)).isoformat()
    data = {
        "registration": registration,
        "model": model,
        "garage": garage,
        "availability_status": "Operational",
        "severity": "Low",
        "issue": "No active defect",
        "scenario": "engine",
        "vor_days": 0,
        "workflow_current_step": 0,
        "next_action": "No action required",
        "responsible": "Alex Tym",
        "action_due": future,
        "mot_due": future,
        "inspection_due": future,
        "service_due": future,
        "odometer_miles": 0,
        "unread_count": 0,
        "is_archived": 0,
        "last_service_date": date.today().isoformat(),
    }
    columns = list(db.execute("PRAGMA table_info(vehicles)"))
    vals: dict[str, object] = {}
    for col in columns:
        name, _, not_null, default, primary_key = col[1], col[2], col[3], col[4], col[5]
        if primary_key:
            continue
        if name in data:
            vals[name] = data[name]
        elif not_null and default is None:
            raise ValueError(f"Missing mandatory vehicle column: {name}")
    columns_sql = ",".join('"' + c.replace('"', '""') + '"' for c in vals)
    placeholders = ",".join("?" for _ in vals)
    cur = db.execute(
        f"INSERT INTO vehicles ({columns_sql}) VALUES ({placeholders})", tuple(vals.values())
    )
    vehicle_id = int(cur.lastrowid)
    _status_baseline(db, vehicle_id, "Operational")
    db.execute(
        "INSERT INTO vor_asset_events(vehicle_id,action,actor,details,created_at) VALUES (?,?,?,?,?)",
        (
            vehicle_id,
            "registered",
            "Fleet Hub",
            json.dumps({"registration": registration}),
            utcnow(),
        ),
    )
    return vehicle_id


def _existing(db: sqlite3.Connection, registration: str) -> sqlite3.Row | None:
    canonical = re.sub(r"\s+", "", registration).upper()
    return db.execute(
        "SELECT id,registration,model,garage,is_archived FROM vehicles WHERE replace(upper(registration),' ','')=?",
        (canonical,),
    ).fetchone()


def register_vehicle(registration: str, model: str, garage: str) -> dict:
    reg = normalise_reg(registration)
    model, garage = model.strip(), garage.strip()
    if not (1 <= len(model) <= 120 and 1 <= len(garage) <= 100):
        raise ValueError("Model and garage are required (max 120/100 characters)")
    with database() as db:
        if _existing(db, reg):
            raise ValueError("Vehicle already registered")
        pk = _add_vehicle(db, reg, model, garage)
        db.commit()
        return {"id": pk, "registration": reg}


def archive_vehicle(vehicle_id: int, archived: bool) -> dict:
    with database() as db:
        row = db.execute(
            "SELECT id,is_archived,registration FROM vehicles WHERE id=?", (vehicle_id,)
        ).fetchone()
        if not row:
            raise ValueError("Vehicle not found")
        if bool(row["is_archived"]) == archived:
            return {"ok": True, "changed": False}
        if (
            archived
            and db.execute(
                "SELECT 1 FROM vor_cases WHERE vehicle_id=? AND status='open' LIMIT 1",
                (vehicle_id,),
            ).fetchone()
        ):
            raise ValueError("Open defect case exists; close it before archiving the asset")
        db.execute("UPDATE vehicles SET is_archived=? WHERE id=?", (int(archived), vehicle_id))
        db.execute(
            "INSERT INTO vor_asset_events(vehicle_id,action,actor,details,created_at) VALUES (?,?,?,?,?)",
            (
                vehicle_id,
                "archived" if archived else "restored",
                "Fleet Department",
                None,
                utcnow(),
            ),
        )
        db.commit()
        return {"ok": True, "changed": True}


def update_status(vehicle_id: int, status: str, actor: str, reason: str, reference: str) -> dict:
    """Manual Fleet confirmation in synthetic KEY2 register; no external writes."""
    if status not in {"VOR", "Operational"}:
        raise ValueError("Unsupported status")
    if actor.strip() != "Fleet Department":
        raise ValueError("Manual confirmation must be by Fleet Department")
    if not reason.strip():
        raise ValueError("Reason is required")
    with database() as db:
        row = db.execute(
            "SELECT availability_status FROM vehicles WHERE id=?", (vehicle_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Vehicle not found")
        old = row["availability_status"]
        if old == status:
            return {"ok": True, "changed": False}
        now = utcnow()
        db.execute(
            "UPDATE vehicles SET availability_status=?,vor_days=CASE WHEN ?='Operational' THEN 0 ELSE vor_days END WHERE id=?",
            (status, status, vehicle_id),
        )
        db.execute(
            """INSERT INTO vor_status_events
          (vehicle_id,old_status,new_status,event_kind,actor,source,reason,external_reference,effective_at,recorded_at)
          VALUES (?,?,?,'manual',?,'Fleet Department',?,?,?,?)""",
            (vehicle_id, old, status, actor, reason.strip(), reference.strip() or None, now, now),
        )
        db.commit()
        return {"ok": True, "changed": True}


def register_list(include_archived: bool = False) -> dict:
    with database() as db:
        where = "" if include_archived else "WHERE is_archived=0"
        return {
            "vehicles": [
                dict(r)
                for r in db.execute(
                    f"SELECT id,registration,model,garage,availability_status,is_archived FROM vehicles {where} ORDER BY registration"
                )
            ],
            "cases": [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM vor_cases ORDER BY opened_at DESC,id DESC LIMIT 500"
                )
            ],
            "statuses": [
                dict(r)
                for r in db.execute("SELECT * FROM vor_status_events ORDER BY id DESC LIMIT 500")
            ],
            "batches": [
                dict(r)
                for r in db.execute("SELECT * FROM vor_import_batches ORDER BY id DESC LIMIT 30")
            ],
            "asset_events": [
                dict(r)
                for r in db.execute("SELECT * FROM vor_asset_events ORDER BY id DESC LIMIT 500")
            ],
        }


def _xlsx_rows(data: bytes) -> list[list[str]]:
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            members = z.infolist()
            if len(members) > 200 or sum(f.file_size for f in members) > MAX_XML_BYTES:
                raise ValueError("XLSX exceeds safe size limits")
            for member in members:
                if member.flag_bits & 0x1:
                    raise ValueError("Encrypted XLSX is not supported")
            workbook = ET.fromstring(z.read("xl/workbook.xml"))
            sheets = workbook.find(ns + "sheets")
            if sheets is None or len(sheets) == 0:
                raise ValueError("XLSX has no worksheets")
            rel_id = sheets[0].get(rel_ns + "id")
            relationships = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            targets = {item.get("Id"): item.get("Target", "") for item in relationships}
            target = targets.get(rel_id, "")
            if not target:
                raise ValueError("Worksheet relationship is missing")
            import posixpath

            worksheet = (
                target.lstrip("/")
                if target.startswith("/")
                else posixpath.normpath(posixpath.join("xl", target))
            )
            if not worksheet.startswith("xl/worksheets/") or ".." in worksheet.split("/"):
                raise ValueError("Unsafe worksheet reference")
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                string_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(x.text or "" for x in si.iter(ns + "t"))
                    for si in string_root.findall(ns + "si")
                ]
            root = ET.fromstring(z.read(worksheet))
            rows = []
            for row in root.iter(ns + "row"):
                if len(rows) > MAX_ROWS:
                    raise ValueError("Too many spreadsheet rows")
                values = {}
                for cell in row.findall(ns + "c"):
                    if cell.find(ns + "f") is not None:
                        raise ValueError("Formula cells are not accepted in imports")
                    ref = cell.get("r", "")
                    match = re.match(r"[A-Z]+", ref)
                    if not match:
                        continue
                    index = 0
                    for letter in match.group(0):
                        index = index * 26 + ord(letter) - 64
                    if index > 40:
                        raise ValueError("Too many import columns")
                    typ = cell.get("t", "")
                    if typ == "inlineStr":
                        val = "".join(x.text or "" for x in cell.iter(ns + "t"))
                    else:
                        el = cell.find(ns + "v")
                        val = el.text if el is not None and el.text else ""
                        if typ == "s":
                            try:
                                val = shared[int(val)]
                            except (IndexError, ValueError):
                                raise ValueError("Invalid shared string reference") from None
                    values[index - 1] = val
                if values:
                    rows.append([values.get(i, "") for i in range(max(values) + 1)])
            return rows
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("Invalid XLSX workbook") from exc


def _parse(data: bytes, filename: str) -> list[dict[str, str]]:
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("File must be between 1 byte and 2 MB")
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("CSV must be UTF-8 encoded") from None
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        cells = list(csv.reader(io.StringIO(text), dialect))
    elif suffix == ".xlsx":
        cells = _xlsx_rows(data)
    else:
        raise ValueError("Only .csv and .xlsx are supported")
    if not cells:
        raise ValueError("File is empty")
    if len(cells) > MAX_ROWS + 1:
        raise ValueError(f"Maximum {MAX_ROWS} rows allowed")
    headers = [normalise_header(x) for x in cells[0]]
    mapping = {}
    for name, aliases in HEADER_ALIASES.items():
        matching = [i for i, x in enumerate(headers) if x in aliases]
        if len(matching) != 1:
            raise ValueError(f"Required unique column missing: {name}")
        mapping[name] = matching[0]
    output = []
    for lineno, row in enumerate(cells[1:], 2):
        if not any(str(c).strip() for c in row):
            continue
        values = {
            name: str(row[index]).strip() if index < len(row) else ""
            for name, index in mapping.items()
        }
        values["row_number"] = str(lineno)
        output.append(values)
    if not output:
        raise ValueError("No vehicle rows found")
    return output


def prepare_import(filename: str, content_b64: str, mode: str) -> dict:
    if mode not in {"skip", "update"}:
        raise ValueError("Mode must be skip or update")
    if len(content_b64) > ((MAX_FILE_BYTES + 2) // 3) * 4 + 16:
        raise ValueError("File too large")
    try:
        binary = base64.b64decode(content_b64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid file encoding") from exc
    source = _parse(binary, filename)
    errors = []
    rows = []
    seen = set()
    for r in source:
        try:
            reg = normalise_reg(r["registration"])
            model = r["model"].strip()
            garage = r["garage"].strip()
            if not 1 <= len(model) <= 120 or not 1 <= len(garage) <= 100:
                raise ValueError("Model/garage cannot be empty or oversized")
            if reg in seen:
                raise ValueError("Duplicate registration within file")
            seen.add(reg)
            rows.append(
                {
                    "registration": reg,
                    "model": model,
                    "garage": garage,
                    "row_number": r["row_number"],
                }
            )
        except ValueError:
            # Never return exception text in a user-visible import preview.
            errors.append({"row": r["row_number"], "error": "Invalid row data"})
    sha = hashlib.sha256(binary).hexdigest()
    with database() as db:
        existing = {
            re.sub(r"\s+", "", r["registration"]).upper(): dict(r)
            for r in db.execute("SELECT id,registration,model,garage,is_archived FROM vehicles")
        }
        previously = db.execute(
            "SELECT id FROM vor_import_batches WHERE digest=? AND mode=?", (sha, mode)
        ).fetchone()
    for r in rows:
        old = existing.get(r["registration"].replace(" ", ""))
        r["action"] = (
            ("skip" if mode == "skip" else "update")
            if old and (old["model"], old["garage"]) != (r["model"], r["garage"])
            else ("skip" if old else "insert")
        )
    return {
        "digest": sha,
        "filename": Path(filename).name[:180],
        "mode": mode,
        "rows": rows,
        "errors": errors,
        "repeated": previously is not None,
        "count": len(rows),
        "preview": rows[:100],
        "summary": {
            name: sum(1 for r in rows if r["action"] == name)
            for name in ("insert", "update", "skip")
        },
    }


def commit_import(filename: str, content_b64: str, mode: str, expected_digest: str) -> dict:
    prepared = prepare_import(filename, content_b64, mode)
    if prepared["digest"] != expected_digest:
        raise ValueError("Import file changed since preview")
    if prepared["errors"]:
        raise ValueError("Import has validation errors")
    with database() as db:
        if db.execute(
            "SELECT id FROM vor_import_batches WHERE digest=? AND mode=?", (expected_digest, mode)
        ).fetchone():
            return {"ok": True, "repeated": True, "summary": {"insert": 0, "update": 0, "skip": 0}}
        now = utcnow()
        # Explicit transaction; either the entire import succeeds or none of its rows are persisted.
        db.execute("BEGIN IMMEDIATE")
        # Recheck under the write lock to make concurrent retries idempotent.
        if db.execute(
            "SELECT id FROM vor_import_batches WHERE digest=? AND mode=?", (expected_digest, mode)
        ).fetchone():
            db.rollback()
            return {"ok": True, "repeated": True, "summary": {"insert": 0, "update": 0, "skip": 0}}
        cur = db.execute(
            """INSERT INTO vor_import_batches(digest,mode,filename,created_at,row_count,inserted_count,updated_count,skipped_count)
            VALUES(?,?,?,?,?,?,?,?)""",
            (expected_digest, mode, prepared["filename"], now, len(prepared["rows"]), 0, 0, 0),
        )
        batch_id = int(cur.lastrowid)
        counts = {"insert": 0, "update": 0, "skip": 0}
        try:
            for row in prepared["rows"]:
                old = _existing(db, row["registration"])
                if not old:
                    vid = _add_vehicle(db, row["registration"], row["model"], row["garage"])
                    action = "insert"
                    before = None
                    after = {"model": row["model"], "garage": row["garage"]}
                elif mode == "update" and (old["model"], old["garage"]) != (
                    row["model"],
                    row["garage"],
                ):
                    vid = old["id"]
                    action = "update"
                    before = {"model": old["model"], "garage": old["garage"]}
                    db.execute(
                        "UPDATE vehicles SET model=?,garage=? WHERE id=?",
                        (row["model"], row["garage"], vid),
                    )
                    after = {"model": row["model"], "garage": row["garage"]}
                else:
                    vid = old["id"]
                    action = "skip"
                    before = None
                    after = None
                counts[action] += 1
                db.execute(
                    "INSERT INTO vor_import_audit(batch_id,vehicle_id,registration,action,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        batch_id,
                        vid,
                        row["registration"],
                        action,
                        json.dumps(before),
                        json.dumps(after),
                        now,
                    ),
                )
            db.execute(
                "UPDATE vor_import_batches SET inserted_count=?,updated_count=?,skipped_count=? WHERE id=?",
                (counts["insert"], counts["update"], counts["skip"], batch_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {"ok": True, "repeated": False, "batch_id": batch_id, "summary": counts}
