"""Fleet VOR v1.1: scenario selection, vertical workflow state, responsible assignments."""

from __future__ import annotations

import sqlite3
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.vor import router
from app.api.vor_checklist import CHECKLIST, router as checklist_router
from datetime import date


def _complete_workflow_checklist(client, vehicle_id: int, ticket_id: str) -> None:
    """Complete this ticket's current required checklist before advancing."""
    snapshot = client.get("/api/vor/bootstrap")
    assert snapshot.status_code == 200
    current = next(
        (
            step
            for step in snapshot.json()["steps"]
            if step["ticket_id"] == ticket_id and step["status"] == "current"
        ),
        None,
    )
    assert current is not None
    index = current["step_index"]
    keys = CHECKLIST[index] if index < len(CHECKLIST) else ()
    for key in keys:
        item = {
            "vehicle_id": vehicle_id,
            "ticket_id": ticket_id,
            "step_index": index,
            "key": key,
            "checked": True,
        }
        if key == "diagnosis_date":
            item["value"] = date.today().isoformat()
        response = client.post("/api/vor/checklists", json=item)
        assert response.status_code == 200, response.text


def test_scenario_and_responsible_keep_existing_data(monkeypatch, tmp_path):
    db_file = tmp_path / "vor.sqlite3"
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "Victoria")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(db_file))
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.include_router(checklist_router, prefix="/api")
    with TestClient(app) as c:
        assert c.get("/api/vor/bootstrap").status_code == 401
        assert c.post("/api/vor/login", json={"password": "Victoria"}).status_code == 200
        snapshot = c.get("/api/vor/bootstrap").json()
        assert len(snapshot["vehicles"]) == 20
        assert len(snapshot["workflows"]) >= 10
        owners = {"Alex Tym", "Victoria B.", "Jason W.", "Janine M.", "Gosha T."}
        assert {v["responsible"] for v in snapshot["vehicles"]}.issubset(owners)
        vehicle = next(v for v in snapshot["vehicles"] if v["registration"] == "GX24 KLM")
        ticket = next(
            t
            for t in snapshot["tickets"]
            if t["vehicle_id"] == vehicle["id"] and t["status"] == "open" and t["kind"] == "VOR"
        )
        existing_count = len(snapshot["events"])
        assert (
            c.post(
                "/api/vor/messages",
                json={
                    "vehicle_id": vehicle["id"],
                    "ticket_id": ticket["id"],
                    "kind": "internal",
                    "text": "Keep this note through scenario updates",
                },
            ).status_code
            == 200
        )
        chosen_owner = next(name for name in sorted(owners) if name != vehicle["responsible"])
        assert (
            c.post(
                "/api/vor/responsible", json={"vehicle_id": vehicle["id"], "name": chosen_owner}
            ).status_code
            == 200
        )
        assert (
            c.post(
                "/api/vor/responsible", json={"vehicle_id": vehicle["id"], "name": "Anyone else"}
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/vor/scenario",
                json={"vehicle_id": vehicle["id"], "ticket_id": ticket["id"], "scenario": "tyre"},
            ).status_code
            == 200
        )
        payload = c.get("/api/vor/bootstrap").json()
        updated_ticket = next(t for t in payload["tickets"] if t["id"] == ticket["id"])
        updated_vehicle = next(v for v in payload["vehicles"] if v["id"] == vehicle["id"])
        tyre_stages = [s for s in payload["steps"] if s["ticket_id"] == ticket["id"]]
        assert updated_ticket["scenario"] == "tyre"
        assert updated_ticket["title"] == "Tyre puncture / wear"
        assert updated_vehicle["issue"] == "Tyre puncture / wear"
        assert updated_vehicle["responsible"] == chosen_owner
        assert updated_vehicle["workflow_current_step"] == 0
        assert tyre_stages[0]["status"] == "current"
        assert all(s["status"] == "pending" for s in tyre_stages[1:])
        assert len(tyre_stages) == 6
        assert updated_vehicle["next_action"] == tyre_stages[0]["label"]
        assert len(payload["events"]) >= existing_count + 3
        assert any(
            "Keep this note through scenario updates" in e["body"] for e in payload["events"]
        )
        assert any("Workflow changed" in e["body"] for e in payload["events"])
        _complete_workflow_checklist(c, vehicle["id"], ticket["id"])
        assert (
            c.post(
                "/api/vor/advance", json={"vehicle_id": vehicle["id"], "ticket_id": ticket["id"]}
            ).status_code
            == 200
        )
        payload = c.get("/api/vor/bootstrap").json()
        progress = [s for s in payload["steps"] if s["ticket_id"] == ticket["id"]]
        assert progress[0]["status"] == "done"
        assert progress[1]["status"] == "current"
        assert (
            next(v for v in payload["vehicles"] if v["id"] == vehicle["id"])["next_action"]
            == progress[1]["label"]
        )
        assert (
            c.post(
                "/api/vor/scenario",
                json={
                    "vehicle_id": vehicle["id"],
                    "ticket_id": ticket["id"],
                    "scenario": "unknown",
                },
            ).status_code
            == 422
        )
        closed = next(t for t in payload["tickets"] if t["status"] == "closed")
        assert (
            c.post(
                "/api/vor/scenario",
                json={
                    "vehicle_id": closed["vehicle_id"],
                    "ticket_id": closed["id"],
                    "scenario": "engine",
                },
            ).status_code
            == 422
        )
        with sqlite3.connect(db_file) as db:
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            assert db.execute("SELECT count(*) FROM vor_schema_versions").fetchone()[0] >= 2
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM events WHERE body='Keep this note through scenario updates'"
                ).fetchone()[0]
                == 1
            )
            assert db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0] > 0
        # Repeated startup/snapshot doesn't reset owners or progress.
        again = c.get("/api/vor/bootstrap").json()
        assert (
            next(v for v in again["vehicles"] if v["id"] == vehicle["id"])["responsible"]
            == chosen_owner
        )
        assert (
            next(
                s for s in again["steps"] if s["ticket_id"] == ticket["id"] and s["step_index"] == 1
            )["status"]
            == "current"
        )
