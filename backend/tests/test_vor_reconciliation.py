"""PR-06: independent synthetic source snapshots, review audit, v1 isolation."""

import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from app.services import vor_reconciliation as recon, vor_store, vor_store_v1


@pytest.fixture
def dbs(monkeypatch, tmp_path):
    v2 = tmp_path / "v2.sqlite3"
    v1 = tmp_path / "v1.sqlite3"
    schema = """
      CREATE TABLE vehicles(id INTEGER PRIMARY KEY, registration TEXT UNIQUE NOT NULL,
        availability_status TEXT NOT NULL CHECK(availability_status IN ('VOR','Operational')));
      CREATE TABLE tickets(id TEXT PRIMARY KEY,vehicle_id INTEGER REFERENCES vehicles(id),
        scenario TEXT, title TEXT, hoth_reference TEXT, opened_at TEXT,
        closed_at TEXT, status TEXT);
      INSERT INTO vehicles VALUES(1,'GX24 KLM','VOR');
      INSERT INTO vehicles VALUES(2,'AB26 XYZ','Operational');
      INSERT INTO vehicles VALUES(3,'CD25 ABC','VOR');
    """
    for p in (v1, v2):
        with sqlite3.connect(p) as db:
            db.executescript(schema)

    @contextmanager
    def connection():
        conn = sqlite3.connect(v2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    monkeypatch.setattr(vor_store, "database_path", lambda: v2)
    monkeypatch.setattr(vor_store_v1, "database_path", lambda: v1)
    monkeypatch.setattr(vor_store, "connection", connection)
    return v2, v1


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def test_seed_compare_and_audit_persist_without_status_change(dbs):
    active, frozen = dbs
    pristine = frozen.read_bytes()
    b = recon.batches()
    assert len(b["batches"]) == 2
    result = recon.compare()
    assert result["issue_count"] >= 2
    data = recon.detail()
    assert data["run"]["id"] == result["run_id"]
    assert any(x["category"] == "status_mismatch" for x in data["issues"])
    assert any(x["category"] == "missing_hoth" for x in data["issues"])
    issue = data["issues"][0]
    recon.review(
        issue["id"],
        "acknowledged",
        "Demo reviewer",
        "Fleet team",
        "Status reported by source delayed",
    )
    refreshed = recon.detail()
    assert refreshed["audit"][0]["new_resolution"] == "acknowledged"
    assert refreshed["issues"][0]["resolution"] == "acknowledged" or any(
        x["resolution"] == "acknowledged" for x in refreshed["issues"]
    )
    with sqlite3.connect(active) as db:
        assert [
            row[0] for row in db.execute("SELECT availability_status FROM vehicles ORDER BY id")
        ] == ["VOR", "Operational", "VOR"]
    assert frozen.read_bytes() == pristine


def test_import_snapshot_and_new_comparison_immutable_previous_run(dbs):
    first = recon.compare()
    old = recon.detail(first["run_id"])
    csv_text = "Registration,Status,Reference,Reason\nGX24 KLM,Operational,HT01,Repaired\nAB26 XYZ,Operational,HT02,Clear\nCD25 ABC,VOR,HT03,Repair\n"
    b = recon.upload("hoth", csv_text, "Morning HOTH export", _timestamp())
    assert b["row_count"] == 3
    other = recon.compare()
    assert other["run_id"] != first["run_id"]
    assert recon.detail(first["run_id"]) == old
    assert recon.detail(other["run_id"])["run"]["hoth_batch_id"] == b["batch_id"]


def test_csv_validation_and_safe_review(dbs):
    recon.batches()
    with pytest.raises(ValueError, match="Duplicate registration"):
        recon.parse_csv("Registration,Status\nGX24 KLM,VOR\nGX24KLM,Operational\n")
    with pytest.raises(ValueError, match="Unrecognised"):
        recon.parse_csv("Registration,Status\nGX24 KLM,Broken\n")
    with pytest.raises(ValueError, match="Required CSV columns"):
        recon.parse_csv("Vehicle,Status\nGX24 KLM,VOR\n")
    with pytest.raises(ValueError, match="Unknown source"):
        recon.upload("other", "Registration,Status\nGX24 KLM,VOR\n", "No", _timestamp())
    issue = recon.detail(recon.compare()["run_id"])["issues"][0]
    with pytest.raises(ValueError, match="review note"):
        recon.review(issue["id"], "resolved", "Operator", "Team", "")
    with pytest.raises(ValueError, match="Invalid review decision"):
        recon.review(issue["id"], "invalid", "Operator", "Team", "Meaningful note")


def test_excel_export_is_valid_zip_and_escaped(dbs):
    result = recon.compare()
    issue = recon.detail(result["run_id"])["issues"][0]
    recon.review(issue["id"], "acknowledged", "Operator", "Ops", "=1+2 potentially dangerous")
    payload = recon.export_xlsx(result["run_id"])
    with zipfile.ZipFile(__import__("io").BytesIO(payload)) as z:
        assert z.testzip() is None
        xml = z.read("xl/worksheets/sheet1.xml").decode()
        assert "=1+2 potentially dangerous" in xml
        assert "<f>" not in xml
        assert "xl/styles.xml" in z.namelist()
    assert len(payload) > 1000


def test_stale_sources_and_history(dbs):
    from datetime import timedelta

    old = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    recon.batches()
    created = recon.upload(
        "hoth",
        "Registration,Status\nGX24 KLM,VOR\nAB26 XYZ,Operational\nCD25 ABC,VOR\n",
        "Old report",
        old,
    )
    run = recon.compare()
    data = recon.detail(run["run_id"])
    assert data["sources"]["hoth"]["stale"] is True
    assert data["sources"]["hoth"]["batch_id"] == created["batch_id"]
    assert recon.runs()[0]["id"] == run["run_id"]
    assert recon.runs()[0]["issue_count"] == len(data["issues"])


def test_unknown_registration_flagged_without_creating_vehicle(dbs):
    recon.batches()
    recon.upload(
        "hoth",
        "Registration,Status\nGX24 KLM,VOR\nAB26 XYZ,Operational\nCD25 ABC,VOR\nXY26 ABC,VOR\n",
        "External record",
        _timestamp(),
    )
    run = recon.compare()
    assert any(
        x["category"] == "unregistered" and x["registration"] == "XY26 ABC"
        for x in recon.detail(run["run_id"])["issues"]
    )


def test_csv_export_sanitises_spreadsheet_formulas(dbs):
    run = recon.compare()
    issue = recon.detail(run["run_id"])["issues"][0]
    recon.review(
        issue["id"], "resolved", "Demo operator", "Ops team", '=HYPERLINK("http://invalid.test")'
    )
    content = recon.export_csv(run["run_id"]).decode("utf-8-sig")
    assert "'=HYPERLINK" in content
    assert "Vehicle,Difference,HOTH status" in content
