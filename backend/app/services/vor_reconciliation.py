"""Synthetic v2-only HOTH vs Fleet-register reconciliation.

No real integration; never changes a vehicle's live VOR/Operational status.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from app.services import vor_data

MAX_ROWS = 2500
MAX_CSV_SIZE = 550_000
SOURCES = {"hoth", "fleet"}
DECISIONS = {"open", "acknowledged", "resolved", "not_an_error"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _setup(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS recon_batches (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL CHECK(source IN ('hoth','fleet')),
      imported_at TEXT NOT NULL, source_as_of TEXT NOT NULL,
      label TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 1,
      row_count INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS recon_rows (
      batch_id INTEGER NOT NULL REFERENCES recon_batches(id),
      registration TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('VOR','Operational')),
      reference TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(batch_id,registration)
    );
    CREATE TABLE IF NOT EXISTS recon_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      hoth_batch_id INTEGER NOT NULL REFERENCES recon_batches(id),
      fleet_batch_id INTEGER NOT NULL REFERENCES recon_batches(id),
      matched_count INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS recon_issues (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id INTEGER NOT NULL REFERENCES recon_runs(id),
      registration TEXT NOT NULL,
      category TEXT NOT NULL,
      hoth_status TEXT, fleet_status TEXT, local_status TEXT,
      hoth_reference TEXT, fleet_reference TEXT,
      resolution TEXT NOT NULL DEFAULT 'open' CHECK(resolution IN ('open','acknowledged','resolved','not_an_error')),
      owner TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
      updated_at TEXT,
      UNIQUE(run_id,registration)
    );
    CREATE INDEX IF NOT EXISTS idx_recon_issues_run ON recon_issues(run_id,resolution,category);
    CREATE TABLE IF NOT EXISTS recon_review_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      issue_id INTEGER NOT NULL REFERENCES recon_issues(id),
      old_resolution TEXT NOT NULL, new_resolution TEXT NOT NULL,
      actor TEXT NOT NULL, owner TEXT NOT NULL,
      note TEXT NOT NULL, recorded_at TEXT NOT NULL
    );
    """)


def _normalise_status(value: str) -> str:
    raw = value.strip().casefold().replace("_", " ").replace("-", " ")
    mapping = {
        "vor": "VOR",
        "off road": "VOR",
        "vehicle off road": "VOR",
        "operational": "Operational",
        "available": "Operational",
        "on road": "Operational",
    }
    if raw not in mapping:
        raise ValueError(f"Unrecognised status: {value[:40]}")
    return mapping[raw]


def parse_csv(csv_text: str) -> list[dict[str, str]]:
    if len(csv_text.encode("utf-8")) > MAX_CSV_SIZE:
        raise ValueError("CSV exceeds the maximum supported file size")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise ValueError("CSV needs a header row")
    mapping = {field.strip().lower(): field for field in reader.fieldnames}
    if not {"registration", "status"} <= mapping.keys():
        raise ValueError("Required CSV columns: Registration, Status")
    if len(mapping) != len(reader.fieldnames):
        raise ValueError("Duplicate CSV headers")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_no, record in enumerate(reader, start=2):
        if line_no > MAX_ROWS + 1:
            raise ValueError(f"CSV must contain no more than {MAX_ROWS} records")
        if None in record:
            raise ValueError(f"CSV line {line_no} has too many columns")
        reg = vor_data.normalise_reg(record[mapping["registration"]] or "")
        if reg in seen:
            raise ValueError(f"Duplicate registration at line {line_no}: {reg}")
        seen.add(reg)
        status = _normalise_status(record[mapping["status"]] or "")

        def col(field: str) -> str:
            value = (record.get(mapping[field], "") or "").strip() if field in mapping else ""
            if len(value) > 180 or any(ord(ch) < 32 and ch not in "\t" for ch in value):
                raise ValueError(f"Invalid {field} at line {line_no}")
            return value

        result.append(
            {
                "registration": reg,
                "status": status,
                "reference": col("reference"),
                "reason": col("reason"),
            }
        )
    if not result:
        raise ValueError("CSV has no vehicle rows")
    return result


def _seed(db: sqlite3.Connection) -> None:
    if db.execute("SELECT 1 FROM recon_batches LIMIT 1").fetchone():
        return
    vehicles = db.execute(
        "SELECT registration, availability_status FROM vehicles ORDER BY id"
    ).fetchall()
    if not vehicles:
        return
    base = [
        (str(v["registration"]), _normalise_status(str(v["availability_status"]))) for v in vehicles
    ]
    stamp = utc_now()
    for source in ("hoth", "fleet"):
        rows = []
        for i, (reg, status) in enumerate(base):
            # Small, explicitly synthetic discrepancies so the demo has reviewable cases.
            if source == "hoth" and i == 0:
                status = "Operational" if status == "VOR" else "VOR"
            if source == "hoth" and i == 1:
                continue
            rows.append((reg, status, f"DEMO-{source.upper()}-{i + 1:03}", "Synthetic snapshot"))
        cur = db.execute(
            "INSERT INTO recon_batches(source,imported_at,source_as_of,label,row_count) VALUES(?,?,?,?,?)",
            (source, stamp, stamp, f"Sample {source.upper()} snapshot", len(rows)),
        )
        db.executemany(
            "INSERT INTO recon_rows(batch_id,registration,status,reference,reason) VALUES(?,?,?,?,?)",
            [(cur.lastrowid, *row) for row in rows],
        )
    db.commit()


def batches() -> dict[str, Any]:
    with vor_data.database() as db:
        _setup(db)
        _seed(db)
        all_rows = [dict(x) for x in db.execute("SELECT * FROM recon_batches ORDER BY id DESC")]
        latest = {
            source: next((r for r in all_rows if r["source"] == source), None) for source in SOURCES
        }
        return {"batches": all_rows[:24], "latest": latest}


def upload(source: str, csv_text: str, label: str, source_as_of: str) -> dict[str, Any]:
    if source not in SOURCES:
        raise ValueError("Unknown source")
    if not 1 <= len(label.strip()) <= 100:
        raise ValueError("A descriptive batch label is required")
    try:
        parsed = datetime.fromisoformat(source_as_of.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Snapshot time must include a timezone")
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid snapshot date and time") from exc
    records = parse_csv(csv_text)
    with vor_data.database() as db:
        _setup(db)
        _seed(db)
        cur = db.execute(
            "INSERT INTO recon_batches(source,imported_at,source_as_of,label,row_count) VALUES(?,?,?,?,?)",
            (
                source,
                utc_now(),
                parsed.astimezone(timezone.utc).isoformat(timespec="seconds"),
                label.strip(),
                len(records),
            ),
        )
        db.executemany(
            "INSERT INTO recon_rows(batch_id,registration,status,reference,reason) VALUES(?,?,?,?,?)",
            [
                (cur.lastrowid, r["registration"], r["status"], r["reference"], r["reason"])
                for r in records
            ],
        )
        db.commit()
        return {"batch_id": int(cur.lastrowid), "row_count": len(records)}


def _choose_batches(
    db: sqlite3.Connection, hoth_id: int | None, fleet_id: int | None
) -> tuple[int, int]:
    result = []
    for source, batch_id in [("hoth", hoth_id), ("fleet", fleet_id)]:
        if batch_id is None:
            row = db.execute(
                "SELECT id FROM recon_batches WHERE source=? ORDER BY id DESC LIMIT 1", (source,)
            ).fetchone()
        else:
            row = db.execute(
                "SELECT id FROM recon_batches WHERE id=? AND source=?", (batch_id, source)
            ).fetchone()
        if row is None:
            raise ValueError(f"Missing {source} snapshot")
        result.append(int(row["id"]))
    return result[0], result[1]


def compare(hoth_id: int | None = None, fleet_id: int | None = None) -> dict[str, Any]:
    with vor_data.database() as db:
        _setup(db)
        _seed(db)
        h, f = _choose_batches(db, hoth_id, fleet_id)

        def get_rows(batch_id: int) -> dict[str, sqlite3.Row]:
            return {
                r["registration"]: r
                for r in db.execute("SELECT * FROM recon_rows WHERE batch_id=?", (batch_id,))
            }

        hoth, fleet = get_rows(h), get_rows(f)
        local = {
            r["registration"]: r["availability_status"]
            for r in db.execute("SELECT registration,availability_status FROM vehicles")
        }
        all_regs = set(hoth) | set(fleet) | set(local)
        issues = []
        matches = 0
        for reg in sorted(all_regs):
            a, b = hoth.get(reg), fleet.get(reg)
            hs, fs = (a["status"] if a else None), (b["status"] if b else None)
            own = local.get(reg)
            if reg not in local:
                category = "unregistered"
            elif not a:
                category = "missing_hoth"
            elif not b:
                category = "missing_fleet"
            elif hs != fs:
                category = "status_mismatch"
            elif own != fs:
                category = "local_mismatch"
            else:
                matches += 1
                continue
            issues.append(
                (
                    reg,
                    category,
                    hs,
                    fs,
                    own,
                    a["reference"] if a else None,
                    b["reference"] if b else None,
                )
            )
        cur = db.execute(
            "INSERT INTO recon_runs(created_at,hoth_batch_id,fleet_batch_id,matched_count) VALUES(?,?,?,?)",
            (utc_now(), h, f, matches),
        )
        db.executemany(
            "INSERT INTO recon_issues(run_id,registration,category,hoth_status,fleet_status,local_status,hoth_reference,fleet_reference) VALUES(?,?,?,?,?,?,?,?)",
            [(cur.lastrowid, *x) for x in issues],
        )
        db.commit()
        return {"run_id": int(cur.lastrowid), "matched_count": matches, "issue_count": len(issues)}


def runs() -> list[dict[str, Any]]:
    with vor_data.database() as db:
        _setup(db)
        return [
            dict(x)
            for x in db.execute(
                "SELECT r.*, (SELECT COUNT(*) FROM recon_issues i WHERE i.run_id=r.id) AS issue_count "
                "FROM recon_runs r ORDER BY r.id DESC LIMIT 100"
            )
        ]


def _source_info(db: sqlite3.Connection, batch_id: int) -> dict[str, Any]:
    row = db.execute("SELECT * FROM recon_batches WHERE id=?", (batch_id,)).fetchone()
    if row is None:
        raise ValueError("Snapshot is unavailable")
    as_of = datetime.fromisoformat(row["source_as_of"].replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - as_of.astimezone(timezone.utc)
    return {
        "batch_id": int(row["id"]),
        "label": row["label"],
        "source_as_of": row["source_as_of"],
        "stale": age > timedelta(hours=48),
        "age_hours": max(0, round(age.total_seconds() / 3600, 1)),
    }


def detail(run_id: int | None = None) -> dict[str, Any]:
    with vor_data.database() as db:
        _setup(db)
        _seed(db)
        if run_id is None:
            run = db.execute("SELECT * FROM recon_runs ORDER BY id DESC LIMIT 1").fetchone()
        else:
            run = db.execute("SELECT * FROM recon_runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            return {"run": None, "issues": [], "audit": [], "sources": None}
        issues = [
            dict(x)
            for x in db.execute(
                'SELECT * FROM recon_issues WHERE run_id=? ORDER BY (resolution="open") DESC,category,registration',
                (run["id"],),
            )
        ]
        audit = [
            dict(x)
            for x in db.execute(
                "SELECT a.* FROM recon_review_audit a JOIN recon_issues i ON i.id=a.issue_id WHERE i.run_id=? ORDER BY a.id DESC LIMIT 300",
                (run["id"],),
            )
        ]
        return {
            "run": dict(run),
            "issues": issues,
            "audit": audit,
            "sources": {
                "hoth": _source_info(db, run["hoth_batch_id"]),
                "fleet": _source_info(db, run["fleet_batch_id"]),
            },
        }


def review(issue_id: int, decision: str, actor: str, owner: str, note: str) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError("Invalid review decision")
    if len(actor.strip()) < 2 or len(actor.strip()) > 100:
        raise ValueError("Reviewer name is required")
    if decision != "open" and len(note.strip()) < 5:
        raise ValueError("Provide a review note (at least five characters)")
    if len(note) > 750 or len(owner) > 100:
        raise ValueError("Review note or owner too long")
    with vor_data.database() as db:
        _setup(db)
        issue = db.execute("SELECT * FROM recon_issues WHERE id=?", (issue_id,)).fetchone()
        if not issue:
            raise ValueError("Discrepancy does not exist")
        stamp = utc_now()
        db.execute(
            "UPDATE recon_issues SET resolution=?,owner=?,note=?,updated_at=? WHERE id=?",
            (decision, owner.strip(), note.strip(), stamp, issue_id),
        )
        db.execute(
            "INSERT INTO recon_review_audit(issue_id,old_resolution,new_resolution,actor,owner,note,recorded_at) VALUES(?,?,?,?,?,?,?)",
            (
                issue_id,
                issue["resolution"],
                decision,
                actor.strip(),
                owner.strip(),
                note.strip(),
                stamp,
            ),
        )
        db.commit()
        return {"ok": True}


def _workbook(rows: list[list[str]]) -> bytes:
    """Safe, single-sheet XLSX: all cell values are stored as inline strings."""
    from app.services.vor_exports import _sheet  # existing stdlib-only Excel serializer

    data = _sheet(rows[0], rows[1:]).encode("utf-8")
    types = b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    rels = b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    workbook = b'<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Reconciliation" sheetId="1" r:id="rId1"/></sheets></workbook>'
    workbook_rels = b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    styles = b'<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font/><font><b/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>'
    types = types.replace(
        b"</Types>",
        b'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
    )
    out = io.BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        z.writestr("xl/worksheets/sheet1.xml", data)
        z.writestr("xl/styles.xml", styles)
    return out.getvalue()


def export_xlsx(run_id: int) -> bytes:
    data = detail(run_id)
    if not data["run"]:
        raise ValueError("Comparison run not found")
    columns = [
        "Vehicle",
        "Difference",
        "HOTH status",
        "Fleet snapshot status",
        "Local register status",
        "HOTH reference",
        "Fleet reference",
        "Review status",
        "Owner",
        "Review notes",
    ]
    rows = [columns]
    for issue in data["issues"]:
        rows.append(
            [
                str(issue[k] or "")
                for k in (
                    "registration",
                    "category",
                    "hoth_status",
                    "fleet_status",
                    "local_status",
                    "hoth_reference",
                    "fleet_reference",
                    "resolution",
                    "owner",
                    "note",
                )
            ]
        )
    return _workbook(rows)


def export_csv(run_id: int) -> bytes:
    data = detail(run_id)
    if not data["run"]:
        raise ValueError("Comparison run not found")
    columns = [
        "Vehicle",
        "Difference",
        "HOTH status",
        "Fleet snapshot status",
        "Local register status",
        "HOTH reference",
        "Fleet reference",
        "Review status",
        "Owner",
        "Review notes",
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)

    def safe_cell(value: Any) -> str:
        text = str(value or "")
        # Prevent Excel from interpreting untrusted imported values as spreadsheet formulas.
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

    for issue in data["issues"]:
        writer.writerow(
            [
                safe_cell(issue[key])
                for key in (
                    "registration",
                    "category",
                    "hoth_status",
                    "fleet_status",
                    "local_status",
                    "hoth_reference",
                    "fleet_reference",
                    "resolution",
                    "owner",
                    "note",
                )
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")
