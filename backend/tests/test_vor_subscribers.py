"""Active VOR subscriber notifications, allowlisting and overdue-date tests."""

from datetime import date
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.vor import router
from app.services import vor_store


def configure_subscribers(client, vehicle_id):
    """Build independent test subscriber lists instead of relying on seed contacts."""
    snapshot = client.get("/api/vor/bootstrap").json()
    for entry in snapshot["subscriptions"]:
        if entry["vehicle_id"] == vehicle_id and entry["is_subscriber"]:
            response = client.post(
                "/api/vor/subscribers",
                json={
                    "vehicle_id": vehicle_id,
                    "contact_id": entry["contact_id"],
                    "subscribed": False,
                },
            )
            assert response.status_code == 200, response.text
    emails = ("alex@unit.example", "victoria@unit.example", "garage@example.test")
    for index, email in enumerate(emails):
        contact = client.post(
            "/api/vor/contacts",
            json={
                "name": f"Fixture recipient {index}",
                "email": email,
                "role": "external" if index == 2 else "internal",
            },
        )
        assert contact.status_code == 200, contact.text
        subscribed = client.post(
            "/api/vor/subscribers",
            json={"vehicle_id": vehicle_id, "contact_id": contact.json()["id"], "subscribed": True},
        )
        assert subscribed.status_code == 200, subscribed.text
    return set(emails)


def test_subscribers_and_simulated_notification(monkeypatch, tmp_path):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "Victoria")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "vor.sqlite3"))
    monkeypatch.setenv("VOR_DEMO_ALEX_EMAIL", "alex@unit.example")
    monkeypatch.setenv("VOR_DEMO_VICTORIA_EMAIL", "victoria@unit.example")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as c:
        assert c.post("/api/vor/login", json={"password": "Victoria"}).status_code == 200
        snap = c.get("/api/vor/bootstrap").json()
        assert len(snap["vehicles"]) == 20
        v = next(x for x in snap["vehicles"] if x["registration"] == "GX24 KLM")
        expected_emails = configure_subscribers(c, v["id"])
        snap = c.get("/api/vor/bootstrap").json()
        contacts = {x["id"]: x for x in snap["contacts"]}
        subscribed = {
            contacts[item["contact_id"]]["email"]
            for item in snap["subscriptions"]
            if item["vehicle_id"] == v["id"] and item["is_subscriber"]
        }
        assert subscribed == expected_emails
        overdue = sum(
            v[col] < str(date.today())
            for v in snap["vehicles"]
            for col in ("mot_due", "inspection_due", "service_due")
        )
        assert overdue >= 12
        v = next(x for x in snap["vehicles"] if x["registration"] == "GX24 KLM")
        assert v["inspection_due"] < snap["today"]
        ticket = next(
            t for t in snap["tickets"] if t["vehicle_id"] == v["id"] and t["status"] == "open"
        )
        sent = c.post(
            "/api/vor/messages",
            json={
                "vehicle_id": v["id"],
                "ticket_id": ticket["id"],
                "kind": "email",
                "subject": "Parts update",
                "text": "Review quote",
            },
        )
        assert sent.status_code == 200, sent.text
        body = sent.json()
        assert body["delivery"] == "simulated_outgoing"
        assert body["recipient_count"] == 3
        changed = c.get("/api/vor/bootstrap").json()
        event = next(e for e in changed["events"] if e["id"] == body["id"])
        assert event["subject"].startswith(f"[{v['registration']}][{ticket['id']}]")
        assert set(event["recipient_email"].split(",")) == set(body["recipients"])
        assert event["body"] == "Review quote"
        assert c.get("/api/vor/bootstrap").json()["contacts"] == changed["contacts"]


def test_live_send_blocked_until_every_subscriber_allowlisted(monkeypatch, tmp_path):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "Victoria")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "vor.sqlite3"))
    monkeypatch.setenv("VOR_DEMO_ALEX_EMAIL", "alex@unit.example")
    monkeypatch.setenv("VOR_DEMO_VICTORIA_EMAIL", "victoria@unit.example")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "true")
    monkeypatch.setenv("VOR_DEMO_ALLOWED_RECIPIENTS", "alex@unit.example,victoria@unit.example")
    monkeypatch.setenv("RESEND_API_KEY", "fake-do-not-send")
    monkeypatch.setenv("VOR_DEMO_FROM_EMAIL", "demo@example.test")
    monkeypatch.setenv("VOR_DEMO_PUBLIC_URL", "https://alextym.com/fleet-vor-hub")
    called = []

    class Response:
        def raise_for_status(self):
            pass

    def fake_post(url, **kwargs):
        called.append(kwargs["json"])
        return Response()

    monkeypatch.setattr("app.api.vor.httpx.post", fake_post)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as c:
        assert c.post("/api/vor/login", json={"password": "Victoria"}).status_code == 200
        snap = c.get("/api/vor/bootstrap").json()
        v = next(x for x in snap["vehicles"] if x["registration"] == "GX24 KLM")
        configure_subscribers(c, v["id"])
        snap = c.get("/api/vor/bootstrap").json()
        message = {
            "vehicle_id": v["id"],
            "kind": "email",
            "subject": "Please check",
            "text": "Important update",
        }
        blocked = c.post("/api/vor/messages", json=message)
        assert blocked.status_code == 403 and not called
        # In the real demo, remove the non-allowlisted sample external subscriber.
        contacts = {x["id"]: x for x in snap["contacts"]}
        ext = next(
            s
            for s in snap["subscriptions"]
            if s["vehicle_id"] == v["id"] and contacts[s["contact_id"]]["role"] == "external"
        )
        assert (
            c.post(
                "/api/vor/subscribers",
                json={"vehicle_id": v["id"], "contact_id": ext["contact_id"], "subscribed": False},
            ).status_code
            == 200
        )
        sent = c.post("/api/vor/messages", json=message)
        assert sent.status_code == 200, sent.text
        assert sent.json()["recipient_count"] == 2
        assert len(called) == 1
        payload = called[0]
        assert "test demonstration" in payload["text"]
        assert v["registration"] in payload["text"]
        assert "https://alextym.com/fleet-vor-hub" in payload["text"]
        assert set(payload["to"] + payload.get("bcc", [])) == {
            "alex@unit.example",
            "victoria@unit.example",
        }
        assert vor_store.email_count_today() == 2
