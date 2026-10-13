"""v1.3 manage and provider delivery regression tests. No external requests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.vor import router


def client(monkeypatch, tmp_path):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "Victoria")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "fleet.sqlite3"))
    monkeypatch.delenv("VOR_DEMO_ALEX_EMAIL", raising=False)
    monkeypatch.delenv("VOR_DEMO_VICTORIA_EMAIL", raising=False)
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    c = TestClient(app)
    assert c.post("/api/vor/login", json={"password": "Victoria"}).status_code == 200
    return c


def test_manage_edits_existing_contacts_persist_and_subscription(monkeypatch, tmp_path):
    with client(monkeypatch, tmp_path) as c:
        snap = c.get("/api/vor/bootstrap").json()
        v = snap["vehicles"][0]
        alex = next(x for x in snap["contacts"] if x["name"] == "Alex Tym")
        changed = {"name": "Alex Tym", "email": "alex@unit.example", "role": "internal"}
        r = c.post(f"/api/vor/contacts/{alex['id']}/update", json=changed)
        assert r.status_code == 200, r.text
        new = {"name": "Unit Tester", "email": "unit@unit.example", "role": "external"}
        new_resp = c.post("/api/vor/contacts", json=new)
        assert new_resp.status_code == 200, new_resp.text
        cid = new_resp.json()["id"]
        assert (
            c.post(
                "/api/vor/subscribers",
                json={"vehicle_id": v["id"], "contact_id": cid, "subscribed": True},
            ).status_code
            == 200
        )
        snap2 = c.get("/api/vor/bootstrap").json()
        assert (
            next(x for x in snap2["contacts"] if x["id"] == alex["id"])["email"]
            == "alex@unit.example"
        )
        assert {"vehicle_id": v["id"], "contact_id": cid, "is_subscriber": 1} in snap2[
            "subscriptions"
        ]
        # repeated snapshot must not restore placeholders from old env settings
        assert c.get("/api/vor/bootstrap").json()["contacts"] == snap2["contacts"]
        same = c.post(
            f"/api/vor/contacts/{alex['id']}/update",
            json={"name": "Alex Tym", "email": "unit@unit.example", "role": "internal"},
        )
        assert same.status_code == 422


def test_domain_permitted_resend_notice_and_daily_quota(monkeypatch, tmp_path):
    with client(monkeypatch, tmp_path) as c:
        snap = c.get("/api/vor/bootstrap").json()
        v = snap["vehicles"][0]
        for sub in snap["subscriptions"]:
            if sub["vehicle_id"] == v["id"]:
                c.post(
                    "/api/vor/subscribers",
                    json={
                        "vehicle_id": v["id"],
                        "contact_id": sub["contact_id"],
                        "subscribed": False,
                    },
                )
        for name, email in [
            ("Alex T", "alex@unit.example"),
            ("Victoria B", "victoria@unit.example"),
        ]:
            contact = c.post(
                "/api/vor/contacts", json={"name": name, "email": email, "role": "internal"}
            )
            assert contact.status_code == 200, contact.text
            assert (
                c.post(
                    "/api/vor/subscribers",
                    json={
                        "vehicle_id": v["id"],
                        "contact_id": contact.json()["id"],
                        "subscribed": True,
                    },
                ).status_code
                == 200
            )
        monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "true")
        monkeypatch.setenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "unit.example")
        monkeypatch.setenv("VOR_DEMO_ALLOWED_RECIPIENTS", "")
        monkeypatch.setenv("VOR_DEMO_EMAIL_LIMIT", "2")
        monkeypatch.setenv("RESEND_API_KEY", "fake-token")
        monkeypatch.setenv("VOR_DEMO_FROM_EMAIL", "demo@verified.example")
        monkeypatch.setenv("VOR_DEMO_PUBLIC_URL", "https://alextym.com/fleet-vor-hub")
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                pass

        def fake_post(url, **kwargs):
            calls.append(kwargs["json"])
            return FakeResponse()

        monkeypatch.setattr("app.api.vor.httpx.post", fake_post)
        req = {
            "vehicle_id": v["id"],
            "ticket_id": None,
            "kind": "email",
            "subject": "Workshop update",
            "text": "The workshop status has changed.",
        }
        sent = c.post("/api/vor/messages", json=req)
        assert sent.status_code == 200, sent.text
        assert sent.json()["recipient_count"] == 2
        assert len(calls) == 1
        assert set(calls[0]["to"] + calls[0].get("bcc", [])) == {
            "alex@unit.example",
            "victoria@unit.example",
        }
        assert "[%s]" % v["registration"] in calls[0]["subject"]
        assert "https://alextym.com/fleet-vor-hub" in calls[0]["text"]
        assert "test demonstration" in calls[0]["text"]
        assert c.post("/api/vor/messages", json=req).status_code == 429
        assert len(calls) == 1


def test_reject_unapproved_and_unauthenticated_requests(monkeypatch, tmp_path):
    with client(monkeypatch, tmp_path) as c:
        snap = c.get("/api/vor/bootstrap").json()
        v = snap["vehicles"][0]
        monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "true")
        monkeypatch.setenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "unit.example")
        blocked = c.post(
            "/api/vor/messages", json={"vehicle_id": v["id"], "kind": "email", "text": "Demo"}
        )
        assert blocked.status_code == 403
    fresh = TestClient(c.app)
    assert (
        fresh.post(
            "/api/vor/contacts",
            json={"name": "Anybody", "email": "any@unit.example", "role": "external"},
        ).status_code
        == 401
    )


def test_wildcard_allows_different_domains_without_bypassing_quota(monkeypatch, tmp_path):
    """'*' is an explicit opt-in to arbitrary domains, not arbitrary recipients."""
    with client(monkeypatch, tmp_path) as c:
        snap = c.get("/api/vor/bootstrap").json()
        vehicle_id = snap["vehicles"][0]["id"]
        for subscribed in snap["subscriptions"]:
            if subscribed["vehicle_id"] == vehicle_id:
                result = c.post(
                    "/api/vor/subscribers",
                    json={
                        "vehicle_id": vehicle_id,
                        "contact_id": subscribed["contact_id"],
                        "subscribed": False,
                    },
                )
                assert result.status_code == 200, result.text
        addresses = ("test.one@alpha.example", "test.two@beta.example")
        for address in addresses:
            added = c.post(
                "/api/vor/contacts",
                json={
                    "name": address.split("@")[0],
                    "email": address,
                    "role": "external",
                },
            )
            assert added.status_code == 200, added.text
            enabled = c.post(
                "/api/vor/subscribers",
                json={
                    "vehicle_id": vehicle_id,
                    "contact_id": added.json()["id"],
                    "subscribed": True,
                },
            )
            assert enabled.status_code == 200, enabled.text

        monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "true")
        monkeypatch.setenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "*")
        monkeypatch.setenv("VOR_DEMO_ALLOWED_RECIPIENTS", "")
        monkeypatch.setenv("VOR_DEMO_EMAIL_LIMIT", "2")
        monkeypatch.setenv("RESEND_API_KEY", "fake-test-token")
        monkeypatch.setenv("VOR_DEMO_FROM_EMAIL", "demo@verified.example")
        monkeypatch.setenv("VOR_DEMO_PUBLIC_URL", "https://alextym.com/fleet-vor-hub")
        deliveries = []

        class FakeResponse:
            def raise_for_status(self):
                return None

        def fake_post(url, **kwargs):
            deliveries.append(kwargs["json"])
            return FakeResponse()

        monkeypatch.setattr("app.api.vor.httpx.post", fake_post)
        message = {
            "vehicle_id": vehicle_id,
            "kind": "email",
            "text": "Test update",
            "subject": "Update",
        }
        sent = c.post("/api/vor/messages", json=message)
        assert sent.status_code == 200, sent.text
        assert sent.json()["recipient_count"] == 2
        assert set(deliveries[0]["to"] + deliveries[0].get("bcc", [])) == set(addresses)
        assert c.post("/api/vor/messages", json=message).status_code == 429
        assert len(deliveries) == 1


def test_wildcard_is_exact_not_partial(monkeypatch, tmp_path):
    """'*.example' is not interpreted as an unrestricted wildcard."""
    with client(monkeypatch, tmp_path) as c:
        snap = c.get("/api/vor/bootstrap").json()
        vehicle_id = snap["vehicles"][0]["id"]
        monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "true")
        monkeypatch.setenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "*.example")
        monkeypatch.setenv("VOR_DEMO_ALLOWED_RECIPIENTS", "")
        response = c.post(
            "/api/vor/messages",
            json={
                "vehicle_id": vehicle_id,
                "kind": "email",
                "text": "Not permitted",
            },
        )
        assert response.status_code == 403, response.text
