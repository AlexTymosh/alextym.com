"""Synthetic VOR demo API contract tests (no provider credentials required)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.vor import router
from app.services import vor_store


def make_client(monkeypatch, tmp):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "Victoria")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp / "demo.sqlite3"))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_seed_and_auth(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path) as client:
        assert client.get("/api/vor/bootstrap").status_code == 401
        assert client.post("/api/vor/login", json={"password": "wrong"}).status_code == 401
        assert client.post("/api/vor/login", json={"password": "Victoria"}).status_code == 200
        result = client.get("/api/vor/bootstrap")
        assert result.status_code == 200
        snapshot = result.json()
        assert len(snapshot["vehicles"]) == 20
        assert len(snapshot["tickets"]) >= 20
        assert len(snapshot["events"]) >= 100
        assert len(snapshot["bookings"]) > 0
        assert client.post("/api/vor/logout").status_code == 200
        assert client.get("/api/vor/bootstrap").status_code == 401


def test_mutations(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path) as client:
        client.post("/api/vor/login", json={"password": "Victoria"})
        payload = client.get("/api/vor/bootstrap").json()
        v = payload["vehicles"][0]
        t = next(
            x for x in payload["tickets"] if x["vehicle_id"] == v["id"] and x["status"] == "open"
        )
        before = len(payload["events"])
        assert (
            client.post(
                "/api/vor/messages",
                json={
                    "vehicle_id": v["id"],
                    "ticket_id": t["id"],
                    "kind": "internal",
                    "text": "Test action",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/vor/messages",
                json={
                    "vehicle_id": v["id"],
                    "ticket_id": t["id"],
                    "kind": "email",
                    "text": "Test email",
                    "recipient": "demo@example.com",
                    "subject": "test",
                },
            ).json()["delivery"]
            == "simulated_outgoing"
        )
        assert len(client.get("/api/vor/bootstrap").json()["events"]) == before + 2
        from datetime import date, timedelta

        future = (date.today() + timedelta(days=90)).isoformat()
        r = client.post(
            "/api/vor/bookings",
            json={
                "vehicle_id": v["id"],
                "kind": "MOT",
                "booked_date": future,
                "garage": "Demo workshop",
            },
        )
        assert r.status_code == 200, r.text
        assert (
            client.post(
                "/api/vor/advance", json={"vehicle_id": v["id"], "ticket_id": t["id"]}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/vor/contacts",
                json={"name": "Test supplier", "email": "supplier@example.com", "role": "external"},
            ).status_code
            == 200
        )
        assert vor_store.email_count_today() == 0
