"""PR-04+05: real SQLite operational controls; frozen v1 must remain byte-identical."""

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

import pytest
from app.services import vor_data, vor_operations as ops, vor_store, vor_store_v1


@pytest.fixture
def dbs(monkeypatch, tmp_path):
    v2 = tmp_path / "active.sqlite3"
    v1 = tmp_path / "frozen.sqlite3"
    schema = """
      PRAGMA foreign_keys=ON;
      CREATE TABLE vehicles(id INTEGER PRIMARY KEY,registration TEXT NOT NULL UNIQUE,model TEXT NOT NULL,
        availability_status TEXT NOT NULL CHECK (availability_status IN ('VOR','Operational')),
        severity TEXT NOT NULL,issue TEXT NOT NULL,scenario TEXT NOT NULL,garage TEXT NOT NULL,
        vor_days INTEGER NOT NULL DEFAULT 0,workflow_current_step INTEGER NOT NULL,
        next_action TEXT NOT NULL,responsible TEXT NOT NULL,action_due TEXT NOT NULL,
        mot_due TEXT NOT NULL,inspection_due TEXT NOT NULL,service_due TEXT NOT NULL,
        last_service_date TEXT NOT NULL,odometer_miles INTEGER NOT NULL,
        unread_count INTEGER NOT NULL,is_demo INTEGER NOT NULL DEFAULT 1);
      CREATE TABLE workflow_templates(code TEXT PRIMARY KEY,name TEXT NOT NULL,steps_json TEXT NOT NULL);
      CREATE TABLE tickets(id TEXT PRIMARY KEY,vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        kind TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,severity TEXT NOT NULL,
        scenario TEXT NOT NULL REFERENCES workflow_templates(code),opened_at TEXT NOT NULL,
        closed_at TEXT,key2_reference TEXT,hoth_reference TEXT,is_demo INTEGER NOT NULL DEFAULT 1);
      CREATE TABLE ticket_steps(ticket_id TEXT NOT NULL REFERENCES tickets(id),step_index INTEGER NOT NULL,
        label TEXT NOT NULL,status TEXT NOT NULL,PRIMARY KEY(ticket_id,step_index));
      CREATE TABLE events(id INTEGER PRIMARY KEY,vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        ticket_id TEXT REFERENCES tickets(id),kind TEXT NOT NULL,author TEXT NOT NULL,body TEXT NOT NULL,
        created_at TEXT NOT NULL,subject TEXT,sender_email TEXT,recipient_email TEXT,direction TEXT,
        external_reference TEXT,is_demo INTEGER NOT NULL DEFAULT 1);
      INSERT INTO workflow_templates VALUES('engine','Engine','["Inspect"]');
      INSERT INTO vehicles(id,registration,model,availability_status,severity,issue,scenario,garage,
        vor_days,workflow_current_step,next_action,responsible,action_due,mot_due,inspection_due,
        service_due,last_service_date,odometer_miles,unread_count)
      VALUES (1,'AB26 XYZ','Ford Transit','VOR','High','No start','engine','Basingstoke',
        4,0,'Inspection','Fleet','2026-11-01','2026-11-01','2026-11-01','2026-11-01','2026-09-01',4000,0);
      INSERT INTO tickets(id,vehicle_id,kind,title,status,severity,scenario,opened_at)
      VALUES ('PS001',1,'DEFECT','No start','open','High','engine','2026-10-20T10:00:00');
      INSERT INTO ticket_steps(ticket_id,step_index,label,status) VALUES('PS001',0,'Defect Registered','current');
      INSERT INTO ticket_steps(ticket_id,step_index,label,status) VALUES('PS001',1,'Diagnosis Scheduled','pending');
      INSERT INTO ticket_steps(ticket_id,step_index,label,status) VALUES('PS001',2,'Awaiting Quotation','pending');
    """
    for p in [v1, v2]:
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


def test_actions_deadlines_blockers_docs_and_v1_integrity(dbs):
    active, frozen = dbs
    before = frozen.read_bytes()
    deadline = (date.today() - timedelta(days=2)).isoformat()
    action = ops.add_action(1, "PS001", "Follow up supplier", "Test User", deadline)
    assert action["id"] > 0
    assert ops.overview()["vehicles"]["1"]["overdue"] == 1
    blocker = ops.add_blocker(1, "PS001", "Parts", "Replacement part not delivered")
    assert ops.overview()["vehicles"]["1"]["blockers"] == 1
    document = ops.add_document(1, "PS001", "Invoice", "INV-001", "received")
    ops.update_document(1, "PS001", document["id"], "verified")
    assert ops.overview()["vehicles"]["1"]["docs_verified"] == 1
    ops.complete_action(1, "PS001", action["id"])
    ops.resolve_blocker(1, "PS001", blocker["id"])
    overview = ops.overview()["vehicles"]["1"]
    assert overview["actions"] == 0 and overview["overdue"] == 0 and overview["blockers"] == 0
    assert ops.queue() == {"actions": [], "blockers": []}
    assert frozen.read_bytes() == before
    assert len(ops.details(1, "PS001")["audit"]) >= 6


def test_explicit_manual_status_and_release_gate(dbs):
    active, frozen = dbs
    with pytest.raises(ValueError, match="confirmation"):
        ops.confirm_status(1, "PS001", "Operational", "Repair confirmed", False)
    with pytest.raises(ValueError, match="checklist incomplete"):
        ops.confirm_status(1, "PS001", "Operational", "Repair confirmed", True)
    for key, _ in ops.CHECKS:
        ops.release_check(1, "PS001", key, True)
    assert ops.overview()["vehicles"]["1"]["release_ready"]
    result = ops.confirm_status(1, "PS001", "Operational", "Vehicle released manually", True)
    assert result["changed"]
    with sqlite3.connect(active) as db:
        assert db.execute("SELECT availability_status FROM vehicles").fetchone()[0] == "Operational"
        event = db.execute(
            "SELECT old_status,new_status,event_kind FROM vor_status_events WHERE event_kind='manual'"
        ).fetchone()
        assert event == ("VOR", "Operational", "manual")
    assert (
        ops.confirm_status(1, "PS001", "Operational", "Repeating confirmation", True)["changed"]
        is False
    )
    assert ops.confirm_status(1, "PS001", "VOR", "New defect reported", True)["changed"]


def test_override_and_stage_skip_are_audited(dbs):
    active, _ = dbs
    assert ops.confirm_status(
        1, "PS001", "Operational", "Emergency override with justification", True, True
    )["changed"]
    with pytest.raises(ValueError, match="min 8"):
        ops.skip_stage(1, "PS001", "Fleet", "no")
    skipped = ops.skip_stage(1, "PS001", "Fleet Department", "Step not required for this repair")
    assert skipped["skipped_stage"] == 0
    with sqlite3.connect(active) as db:
        assert (
            db.execute("SELECT status FROM ticket_steps WHERE step_index=0").fetchone()[0]
            == "skipped"
        )
        assert (
            db.execute("SELECT status FROM ticket_steps WHERE step_index=1").fetchone()[0]
            == "current"
        )
        assert db.execute("SELECT COUNT(*) FROM ops_stage_skips").fetchone()[0] == 1


def test_template_required_flags_and_ticket_ownership(dbs):
    active, _ = dbs
    stage = ops.templates()["items"]
    assert stage and any(x["item_key"] == "notification_sent" for x in stage)
    ops.update_template(0, "response_received", "Response received from garage", False)
    with vor_data.database() as db:
        assert "response_received" not in ops.required_keys(db, 0)
    with pytest.raises(ValueError, match="required"):
        ops.update_template(1, "diagnosis_date", "Visit date", False)
    with pytest.raises(ValueError, match="not found"):
        ops.add_action(1, "WRONG", "Call partner", "Tester", date.today().isoformat())
