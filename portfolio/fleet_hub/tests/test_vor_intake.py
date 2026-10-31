"""V2 defect intake tests against realistic SQLite constraints."""

import sqlite3
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api.vor import router as current_router
from fleet_hub.api.vor_intake import router as intake_router
from fleet_hub.services import vor_data, vor_intake, vor_store


@pytest.fixture
def env(monkeypatch, tmp_path):
    active = tmp_path / "active.sqlite3"
    schema = """
      PRAGMA foreign_keys=ON;
      CREATE TABLE vehicles (
        id INTEGER PRIMARY KEY, registration TEXT NOT NULL UNIQUE, model TEXT NOT NULL,
        availability_status TEXT NOT NULL CHECK (availability_status IN ('VOR','Operational')),
        severity TEXT NOT NULL, issue TEXT NOT NULL, scenario TEXT NOT NULL,garage TEXT NOT NULL,
        vor_days INTEGER NOT NULL DEFAULT 0, workflow_current_step INTEGER NOT NULL,
        next_action TEXT NOT NULL,responsible TEXT NOT NULL,action_due TEXT NOT NULL,
        mot_due TEXT NOT NULL, inspection_due TEXT NOT NULL,service_due TEXT NOT NULL,
        last_service_date TEXT NOT NULL, odometer_miles INTEGER NOT NULL,
        unread_count INTEGER NOT NULL,maintenance_scheduled INTEGER NOT NULL DEFAULT 0,
        is_demo INTEGER NOT NULL DEFAULT 1);
      CREATE TABLE workflow_templates(code TEXT PRIMARY KEY,name TEXT NOT NULL,steps_json TEXT NOT NULL);
      CREATE TABLE tickets (id TEXT PRIMARY KEY,vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        kind TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,severity TEXT NOT NULL,
        scenario TEXT NOT NULL REFERENCES workflow_templates(code),opened_at TEXT NOT NULL,
        closed_at TEXT,key2_reference TEXT,hoth_reference TEXT,is_demo INTEGER NOT NULL DEFAULT 1);
      CREATE TABLE ticket_steps(ticket_id TEXT NOT NULL REFERENCES tickets(id),step_index INTEGER NOT NULL,
        label TEXT NOT NULL,status TEXT NOT NULL,PRIMARY KEY(ticket_id,step_index));
      CREATE TABLE events (id INTEGER PRIMARY KEY,vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        ticket_id TEXT REFERENCES tickets(id),kind TEXT NOT NULL,author TEXT NOT NULL,body TEXT NOT NULL,
        created_at TEXT NOT NULL,subject TEXT,sender_email TEXT,recipient_email TEXT,direction TEXT,
        external_reference TEXT,is_demo INTEGER NOT NULL DEFAULT 1);
      INSERT INTO workflow_templates VALUES('engine','Engine','["Inspect"]');
      INSERT INTO vehicles (id,registration,model,availability_status,severity,issue,scenario,garage,
        vor_days,workflow_current_step,next_action,responsible,action_due,mot_due,inspection_due,
        service_due,last_service_date,odometer_miles,unread_count)
      VALUES(1,'GX24 KLM','Ford Transit 350','Operational','Low','No active defect','engine','Nursling',
        0,0,'None','Alex Tym','2026-11-01','2026-11-01','2026-11-01','2026-11-01','2026-09-01',24000,0);
    """
    with sqlite3.connect(active) as db:
        db.executescript(schema)
        db.commit()

    @contextmanager
    def patched_connection():
        with sqlite3.connect(active, timeout=15) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            yield db

    monkeypatch.setattr(vor_store, "database_path", lambda: active)
    monkeypatch.setattr(vor_store, "connection", patched_connection)
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "test-secret")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    return active


def body(pathway="standard", **changes):
    record = {
        "vehicle_id": 1,
        "pathway": pathway,
        "reason": "Mechanical",
        "description": "Engine stalls at junctions",
        "hoth_reference": "HOTH-204",
        "source": "outlook",
        "reported_vor": True,
        "roadside_reported": False,
        "request_id": str(uuid4()),
    }
    record.update(changes)
    return record


def test_standard_creates_tracking_ticket_and_eight_steps_without_status_change(env):
    active = env
    result = vor_intake.register_defect(**body())
    assert result["ticket_id"].startswith("PS")
    assert result["requires_pts_workflow"] is True
    with sqlite3.connect(active) as db:
        assert (
            db.execute("SELECT availability_status FROM vehicles WHERE id=1").fetchone()[0]
            == "Operational"
        )
        assert db.execute("SELECT COUNT(*) FROM ticket_steps").fetchone()[0] == 8
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        assert db.execute("SELECT reported_vor FROM vor_cases").fetchone()[0] == 1


def test_specialist_cases_no_pts_stages(env):
    for pathway in ("tyres", "windscreen"):
        response = vor_intake.register_defect(**body(pathway, hoth_reference=f"HOTH-{pathway}"))
        assert response["requires_pts_workflow"] is False
    with sqlite3.connect(env) as db:
        assert db.execute("SELECT COUNT(*) FROM vor_cases").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM ticket_steps").fetchone()[0] == 0
        assert db.execute("SELECT availability_status FROM vehicles").fetchone()[0] == "Operational"


def test_idempotent_retry_and_original_cases(env):
    params = body()
    one = vor_intake.register_defect(**params)
    two = vor_intake.register_defect(**params)
    assert two["repeated"] is True
    assert one["case_id"] == two["case_id"]
    with sqlite3.connect(env) as db:
        assert db.execute("SELECT COUNT(*) FROM vor_cases").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    with pytest.raises(ValueError, match="reused"):
        vor_intake.register_defect(**{**params, "pathway": "tyres"})
    with pytest.raises(ValueError, match="reused"):
        vor_intake.register_defect(**{**params, "description": "Different details"})


def test_roadside_case_and_invalid_reason(env):
    resp = vor_intake.register_defect(**body(roadside_reported=True))
    assert resp["case_id"] > 0
    with sqlite3.connect(env) as db:
        assert db.execute("SELECT roadside_reported FROM vor_cases").fetchone()[0] == 1
    with pytest.raises(ValueError, match="reason"):
        vor_intake.register_defect(**body(reason="COMMS"))
    with pytest.raises(ValueError, match="reason"):
        vor_intake.register_defect(**body(reason="Misfuelled"))


def test_duplicate_hoth_reference_for_vehicle_is_rejected(env):
    vor_intake.register_defect(**body())
    with pytest.raises(ValueError, match="HOTH reference already"):
        vor_intake.register_defect(**body(description="Second report for the same HOTH ticket"))


def test_archived_asset_and_bad_vehicle_rejected(env):
    vor_data.archive_vehicle(1, True)
    with pytest.raises(ValueError, match="archived"):
        vor_intake.register_defect(**body())
    with pytest.raises(ValueError, match="not exist"):
        vor_intake.register_defect(**body(vehicle_id=99))


def test_api_auth_and_no_automatic_email(env):
    app = FastAPI()
    app.include_router(current_router, prefix="/api")
    app.include_router(intake_router, prefix="/api")
    with TestClient(app) as c:
        assert c.get("/api/vor/intake/options").status_code == 401
        assert c.post("/api/vor/login", json={"password": "test-secret"}).status_code == 200
        response = c.get("/api/vor/intake/options")
        assert response.status_code == 200
        assert response.json()["vehicles"][0]["registration"] == "GX24 KLM"
        response = c.post("/api/vor/intake/defects", json=body())
        assert response.status_code == 201, response.text
        assert response.json()["availability_changed"] is False


def test_v2_real_seed_status_constraint_for_import(env):
    added = vor_data.register_vehicle("AB26 XYZ", "Transit", "Oxford")
    with sqlite3.connect(env) as db:
        assert (
            db.execute(
                "SELECT availability_status FROM vehicles WHERE id=?", (added["id"],)
            ).fetchone()[0]
            == "Operational"
        )
