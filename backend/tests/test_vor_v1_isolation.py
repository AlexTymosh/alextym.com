"""PR-01 regression: frozen v1 and active v2 have independent DBs and login state."""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.vor import router as v2_router
from app.api.vor_v1 import router as v1_router
from app.services import vor_store


def test_frozen_api_login_and_bidirectional_mutations(monkeypatch, tmp_path):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "fixture-secret-not-a-production-password")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    monkeypatch.setenv("VOR_V1_SEND_REAL_EMAIL", "false")
    v2_path = tmp_path / "active.sqlite3"
    v1_path = tmp_path / "frozen.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(v2_path))
    monkeypatch.setenv("VOR_V1_DB_PATH", str(v1_path))

    # Produce a fully migrated baseline once; every v1 row is copied from it.
    with vor_store.connection():
        pass
    with sqlite3.connect(v2_path) as active, sqlite3.connect(v1_path) as frozen:
        active.backup(frozen)

    app = FastAPI()
    app.include_router(v1_router, prefix="/api")
    app.include_router(v2_router, prefix="/api")
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/vor-01/login", json={"password": "fixture-secret-not-a-production-password"}
            ).status_code
            == 200
        )
        assert client.get("/api/vor-01/bootstrap").status_code == 200
        # Version-specific path and cookie: v1 login MUST NOT unlock v2.
        assert client.get("/api/vor/bootstrap").status_code == 401
        assert (
            client.post(
                "/api/vor/login", json={"password": "fixture-secret-not-a-production-password"}
            ).status_code
            == 200
        )
        assert client.get("/api/vor/bootstrap").status_code == 200
        assert client.cookies.get("vor_demo_session")
        assert client.cookies.get("vor_01_demo_session")

        def read(path):
            resp = client.get(path)
            assert resp.status_code == 200, resp.text
            return resp.json()

        v1_path_api = "/api/vor-01/bootstrap"
        v2_path_api = "/api/vor/bootstrap"
        v1_before, v2_before = read(v1_path_api), read(v2_path_api)
        # PR-02 adds v2-only vehicle metadata (is_archived). The frozen v1
        # schema must NOT be migrated just to make these dictionaries equal.
        # Compare every original v1 field and all unchanged collections instead.
        assert v1_before.keys() == v2_before.keys()
        assert {k: v for k, v in v1_before.items() if k != "vehicles"} == {
            k: v for k, v in v2_before.items() if k != "vehicles"
        }
        assert len(v1_before["vehicles"]) == len(v2_before["vehicles"])
        for legacy, active in zip(v1_before["vehicles"], v2_before["vehicles"]):
            assert all(active.get(field) == value for field, value in legacy.items())
            assert "is_archived" not in legacy
            assert active["is_archived"] == 0
        vehicle = v1_before["vehicles"][0]
        reg = vehicle["registration"]
        open_tickets = [
            t
            for t in v1_before["tickets"]
            if t["vehicle_id"] == vehicle["id"] and t["status"] == "open"
        ]

        # Write to frozen v1 and verify v2's *entire* snapshot is unchanged.
        requests = [
            (
                "/api/vor-01/messages",
                {
                    "vehicle_id": vehicle["id"],
                    "ticket_id": None,
                    "kind": "internal",
                    "text": "Legacy-only regression marker",
                },
            ),
            (
                "/api/vor-01/bookings",
                {
                    "vehicle_id": vehicle["id"],
                    "kind": "MOT",
                    "booked_date": "2031-12-31",
                    "garage": "Regression Garage",
                },
            ),
            (
                "/api/vor-01/contacts",
                {
                    "name": "Legacy Test Contact",
                    "email": "legacy-contact@example.invalid",
                    "role": "external",
                },
            ),
        ]
        legacy_contact_id = None
        for url, body in requests:
            response = client.post(url, json=body)
            assert response.status_code == 200, (url, response.text)
            if url.endswith("/contacts"):
                legacy_contact_id = response.json()["id"]
        assert legacy_contact_id is not None
        r = client.post(
            "/api/vor-01/subscribers",
            json={
                "vehicle_id": vehicle["id"],
                "contact_id": legacy_contact_id,
                "subscribed": True,
            },
        )
        assert r.status_code == 200, r.text
        if open_tickets:
            r = client.post(
                "/api/vor-01/advance",
                json={"vehicle_id": vehicle["id"], "ticket_id": open_tickets[0]["id"]},
            )
            assert r.status_code == 200, r.text
        assert read(v2_path_api) == v2_before
        assert read(v1_path_api) != v1_before

        # Independently mutate v2; no back-propagation into frozen v1.
        frozen_after = read(v1_path_api)
        r = client.post(
            "/api/vor/workshop", json={"vehicle_id": vehicle["id"], "garage": "Other Garage"}
        )
        assert r.status_code == 200, r.text
        r = client.post(
            "/api/vor/messages",
            json={
                "vehicle_id": vehicle["id"],
                "ticket_id": None,
                "kind": "internal",
                "text": "Active-only regression marker",
            },
        )
        assert r.status_code == 200, r.text
        assert read(v1_path_api) == frozen_after
        assert read(v2_path_api) != v2_before

        # Both independent legacy export endpoints are still available.
        for prefix in ("/api/vor", "/api/vor-01"):
            excel = client.get(f"{prefix}/export.xlsx")
            assert excel.status_code == 200 and excel.content.startswith(b"PK"), (
                excel.text[:180] if excel.status_code != 200 else ""
            )
            calendar = client.get(f"{prefix}/calendar.ics")
            assert calendar.status_code == 200 and b"BEGIN:VCALENDAR" in calendar.content

        # Logging out of legacy v1 must not affect v2's session.
        assert client.post("/api/vor-01/logout").status_code == 200
        assert client.get("/api/vor-01/bootstrap").status_code == 401
        assert client.get("/api/vor/bootstrap").status_code == 200
        assert any(
            e["body"] == "Active-only regression marker" for e in read(v2_path_api)["events"]
        )
        assert not any(e["body"] == "Active-only regression marker" for e in frozen_after["events"])
        assert any(e["body"] == "Legacy-only regression marker" for e in frozen_after["events"])
        assert (
            client.post(
                "/api/vor-01/login", json={"password": "fixture-secret-not-a-production-password"}
            ).status_code
            == 200
        )
        assert client.post("/api/vor/logout").status_code == 200
        assert client.get("/api/vor/bootstrap").status_code == 401
        assert client.get("/api/vor-01/bootstrap").status_code == 200
        assert reg
