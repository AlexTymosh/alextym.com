"""Regression tests: v2 checklists persist and cannot release vehicles automatically."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.vor import router as vor_router
from app.api.vor_checklist import router as checklist_router, CHECKLIST
from app.services import vor_store


def test_persisted_checklist_blocks_until_complete_and_never_changes_vor(monkeypatch, tmp_path):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "fixture-secret")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "v2.sqlite3"))
    with vor_store.connection() as db:
        current = db.execute("""SELECT t.id,t.vehicle_id,s.step_index
          FROM tickets t JOIN ticket_steps s ON s.ticket_id=t.id
          WHERE t.status='open' AND s.status='current' AND s.step_index < 8 LIMIT 1""").fetchone()
        assert current is not None
        ticket_id, vehicle_id, index = current["id"], current["vehicle_id"], current["step_index"]
        initial = db.execute("SELECT availability_status FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()[0]
    app=FastAPI()
    app.include_router(vor_router,prefix="/api")
    app.include_router(checklist_router,prefix="/api")
    with TestClient(app) as client:
        assert client.post("/api/vor/login",json={"password":"fixture-secret"}).status_code==200
        check_url=f"/api/vor/checklists/{ticket_id}"
        assert client.get(check_url).json()=={"items": []}
        move_url="/api/vor/checklists/advance"
        advance={"ticket_id":ticket_id,"vehicle_id":vehicle_id}
        assert client.post(move_url,json=advance).status_code==409
        invalid={"ticket_id":ticket_id,"vehicle_id":vehicle_id,"step_index":index,"key":"invented","checked":True}
        assert client.post("/api/vor/checklists",json=invalid).status_code==422
        for item in CHECKLIST[index]:
            payload={"ticket_id":ticket_id,"vehicle_id":vehicle_id,"step_index":index,"key":item,"checked":True}
            if item=="diagnosis_date":payload["value"]="2026-11-20"
            assert client.post("/api/vor/checklists",json=payload).status_code==200
        saved=client.get(check_url).json()["items"]
        assert len(saved)==len(CHECKLIST[index])
        assert all(x["checked"] for x in saved)
        assert client.post(move_url,json=advance).status_code==200
        with vor_store.connection() as db:
            after=db.execute("SELECT availability_status FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()[0]
            assert after==initial
