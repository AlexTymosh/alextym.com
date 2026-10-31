"""Active Fleet VOR seed, migration and downloadable export regression tests."""

from __future__ import annotations

import re
import sqlite3
import zipfile
from io import BytesIO
from datetime import date, timedelta
import xml.etree.ElementTree as ET

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api.vor import router


def client(monkeypatch, tmp_path):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "Victoria")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "vor.sqlite3"))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_refresh_and_download(monkeypatch, tmp_path):
    with client(monkeypatch, tmp_path) as c:
        assert c.get("/api/vor/export.xlsx").status_code == 401
        assert c.get("/api/vor/calendar.ics").status_code == 401
        assert c.post("/api/vor/login", json={"password": "Victoria"}).status_code == 200
        body = c.get("/api/vor/bootstrap").json()
        assert len(body["vehicles"]) == 20
        assert len(body["tickets"]) == 42
        assert all(re.fullmatch(r"PS000\d{3}", t["id"]) for t in body["tickets"])
        assert len({t["id"] for t in body["tickets"]}) == len(body["tickets"])
        assert not any("iveco" in v["model"].lower() for v in body["vehicles"])
        assert sum(v["model"].startswith("Tesla") for v in body["vehicles"]) >= 2
        contact_lookup = {x["id"]: x for x in body["contacts"]}
        vehicle_ids = {v["id"] for v in body["vehicles"]}
        assert body["subscriptions"]
        assert all(
            item["vehicle_id"] in vehicle_ids
            and item["contact_id"] in contact_lookup
            and contact_lookup[item["contact_id"]]["role"] in {"internal", "external"}
            for item in body["subscriptions"]
        )

        x = c.get("/api/vor/export.xlsx")
        assert x.status_code == 200
        assert x.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        z = zipfile.ZipFile(BytesIO(x.content))
        assert z.testzip() is None
        for sheet in (
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
            "xl/worksheets/sheet3.xml",
            "xl/worksheets/sheet4.xml",
            "xl/worksheets/sheet5.xml",
        ):
            ET.fromstring(z.read(sheet))
        workbook = z.read("xl/workbook.xml").decode()
        assert all(
            name in workbook
            for name in ("Vehicles", "Tickets", "Activity", "Bookings", "Subscribers")
        )
        assert "PS000" in z.read("xl/worksheets/sheet2.xml").decode()

        ics = c.get("/api/vor/calendar.ics")
        assert ics.status_code == 200
        assert ics.content.startswith(b"BEGIN:VCALENDAR\r\n")
        assert ics.content.count(b"BEGIN:VEVENT") == len(body["bookings"])
        assert b"LOCATION:" in ics.content

        chosen = body["vehicles"][0]
        ticket = next(t for t in body["tickets"] if t["vehicle_id"] == chosen["id"])
        assert (
            c.post(
                "/api/vor/messages",
                json={
                    "vehicle_id": chosen["id"],
                    "ticket_id": ticket["id"],
                    "kind": "internal",
                    "text": "New note after migration",
                },
            ).status_code
            == 200
        )
        future = (date.today() + timedelta(days=120)).isoformat()
        assert (
            c.post(
                "/api/vor/bookings",
                json={
                    "vehicle_id": chosen["id"],
                    "kind": "MOT",
                    "booked_date": future,
                    "garage": "Demo garage",
                },
            ).status_code
            == 200
        )
        assert c.get("/api/vor/bootstrap").json()["tickets"][0]["id"] in {
            t["id"] for t in body["tickets"]
        }
        stored_path = tmp_path / "vor.sqlite3"
        with sqlite3.connect(stored_path) as db:
            assert db.execute("pragma foreign_key_check").fetchall() == []
            assert db.execute("select count(*) from vor_schema_versions").fetchone()[0] >= 3
            assert (
                db.execute(
                    "select count(*) from events where body=?", ("New note after migration",)
                ).fetchone()[0]
                == 1
            )
            assert (
                db.execute(
                    "select count(*) from maintenance_bookings where garage=?", ("Demo garage",)
                ).fetchone()[0]
                == 1
            )
        assert c.get("/api/vor/bootstrap").json()["tickets"][0]["id"] in {
            t["id"] for t in body["tickets"]
        }
