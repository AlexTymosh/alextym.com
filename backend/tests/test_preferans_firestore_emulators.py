"""Real Admin SDK, host authentication/grants and transactions; opt-in demo only."""

from __future__ import annotations

import os
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth, delete_app, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.security.firebase_identity import _firebase_app
from app.security.project_grants import grant_document

pytestmark = pytest.mark.skipif(
    os.getenv("PREFERANS_EMULATOR_TESTS") != "true",
    reason="Requires explicit opt-in and both localhost Firebase demo emulators",
)


@pytest.fixture
def environment(monkeypatch):
    project = os.getenv("FIREBASE_PROJECT_ID", "")
    assert project.startswith("demo-"), "Emulator tests must never use a real Firebase project"
    assert not os.getenv("RENDER") and not os.getenv("VERCEL")
    for name in ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST"):
        assert re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", os.getenv(name, ""))
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PREFERANS_ROOMS_ENABLED", "true")
    run_id = secrets.token_hex(8)
    uids = [f"preferans-test-{run_id}-{seat}" for seat in range(4)]
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", uids[0])
    _firebase_app.cache_clear()
    app = _firebase_app()
    db = firestore.client(app=app)
    tokens, sessions = [], []
    try:
        for seat, uid in enumerate(uids):
            email = f"{uid}@example.test"
            password = secrets.token_urlsafe(24)
            auth.create_user(uid=uid, email=email, password=password, app=app)
            response = httpx.post(
                f"http://{os.environ['FIREBASE_AUTH_EMULATOR_HOST']}/"
                "identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
                params={"key": project},
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=10,
                trust_env=False,
            )
            response.raise_for_status()
            token = response.json()["idToken"]
            tokens.append(token)
            sessions.append(auth.create_session_cookie(token, timedelta(days=1), app=app))
            db.collection("portfolio_lab_identities").document(uid).set(
                {"schema_version": 1, "uid": uid, "status": "active", "password_state": "user_set"}
            )
            if seat in (1, 2):
                grant_document(db, "preferans", uid).set(
                    {
                        "schema_version": 1,
                        "uid": uid,
                        "project_id": "preferans",
                        "role": "Test" if seat == 1 else "Admin",
                        "status": "active",
                    }
                )
        from app.main import create_app

        # No dependency overrides: use the real host guard, SDK and Firestore.
        with TestClient(create_app()) as client:
            yield client, db, uids, tokens, sessions
    finally:
        db.close()
        delete_app(app)
        _firebase_app.cache_clear()


def credential(kind, seat, environment):
    values = environment[3] if kind == "Bearer" else environment[4]
    return {"Authorization": f"{kind} {values[seat]}"}


@pytest.mark.parametrize("kind", ["Bearer", "FirebaseSession"])
def test_real_sdk_room_lifecycle_empty_queries_and_private_views(environment, kind):
    client, db, uids, _, _ = environment
    admin = credential(kind, 0, environment)
    history = client.get("/api/preferans/history", headers=admin)
    assert history.status_code == 200
    assert history.json() == {
        "results": [],
        "has_more": False,
        "limit": 50,
    }
    rankings = client.get("/api/preferans/rankings", headers=admin)
    assert rankings.status_code == 200
    assert rankings.json() == {"rankings": [], "total_players": 0}
    body = {"idempotency_key": "create-room-emulator-0001"}
    first = client.post("/api/preferans/rooms", headers=admin, json=body)
    assert first.status_code == 201
    room = first.json()["room_id"]
    replay = client.post("/api/preferans/rooms", headers=admin, json=body)
    assert replay.status_code == 201 and replay.json() == first.json()
    rooms = db.collection("preferans_rooms").where(filter=FieldFilter("admin_uid", "==", uids[0]))
    assert len(list(rooms.stream(timeout=5))) == 1
    for seat, version in ((1, 0), (2, 1)):
        joined = client.post(
            f"/api/preferans/rooms/{room}/join",
            headers=credential(kind, seat, environment),
            json={"idempotency_key": f"join-room-emulator-{seat}", "expected_version": version},
        )
        assert joined.status_code == 200 and joined.json()["version"] == version + 1
    assert (
        client.post(
            f"/api/preferans/rooms/{room}/start",
            headers=admin,
            json={"idempotency_key": "early-start-emulator", "expected_version": 2},
        ).status_code
        == 409
    )
    for seat in range(3):
        ready = client.post(
            f"/api/preferans/rooms/{room}/commands",
            headers=credential(kind, seat, environment),
            json={
                "idempotency_key": f"ready-room-emulator-{seat}",
                "expected_version": 2 + seat,
                "action": "lobby_ready",
                "args": {"ready": True},
            },
        )
        assert ready.status_code == 200
    start = client.post(
        f"/api/preferans/rooms/{room}/start",
        headers=admin,
        json={"idempotency_key": "start-room-emulator-0001", "expected_version": 5},
    )
    assert start.status_code == 200
    for seat in range(3):
        response = client.get(
            f"/api/preferans/rooms/{room}/view", headers=credential(kind, seat, environment)
        )
        assert response.status_code == 200
        view = response.json()
        assert view["my_seat"] == seat and len(view["hand"]) == 10
        assert view["phase"] == "auction" and view["open_hands"] == [] and view["widow"] == []
        assert "hands" not in view and "discarded" not in view and "game" not in view
        assert all(uid not in response.text for uid in uids)
    moved = client.post(
        f"/api/preferans/rooms/{room}/commands",
        headers=admin,
        json={
            "idempotency_key": "first-command-emulator-0001",
            "expected_version": 6,
            "action": "pass",
            "args": {},
        },
    )
    assert moved.status_code == 200 and moved.json()["version"] == 7
    assert (
        client.get(f"/api/preferans/rooms/{room}/private/current", headers=admin).status_code == 404
    )
    # Revocation takes effect with the same still-valid Firebase credential.
    grant_document(db, "preferans", uids[1]).update({"status": "revoked"})
    assert (
        client.get(
            f"/api/preferans/rooms/{room}/view", headers=credential(kind, 1, environment)
        ).status_code
        == 403
    )


def test_real_sdk_denies_missing_identity_and_another_project_grant(environment):
    client, db, uids, _, _ = environment
    grant_document(db, "fleet_hub", uids[3]).set(
        {
            "schema_version": 1,
            "uid": uids[3],
            "project_id": "fleet_hub",
            "role": "Admin",
            "status": "active",
        }
    )
    for method, path, body in (
        ("POST", "/api/preferans/rooms", {"idempotency_key": "unauthorized-room-0001"}),
        ("GET", "/api/preferans/history", None),
        ("GET", "/api/preferans/rankings", None),
    ):
        assert client.request(method, path, json=body).status_code == 401
        assert (
            client.request(
                method, path, json=body, headers=credential("Bearer", 3, environment)
            ).status_code
            == 403
        )


def test_real_sdk_concurrent_create_preserves_idempotency_after_contention(environment):
    client, db, uids, _, _ = environment

    def create():
        return client.post(
            "/api/preferans/rooms",
            headers=credential("FirebaseSession", 0, environment),
            json={"idempotency_key": "concurrent-room-emulator-0001"},
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: create(), range(2)))
    # The emulator can exhaust the SDK's five transaction attempts on a lock
    # timeout. Do not claim simultaneous success or hide that real HTTP 503.
    assert all(response.status_code in {201, 503} for response in responses)
    replay = create()
    assert replay.status_code == 201
    for response in responses:
        if response.status_code == 201:
            assert response.json() == replay.json()
        else:
            assert response.json() == {"detail": "Storage unavailable"}
    rooms = db.collection("preferans_rooms").where(filter=FieldFilter("admin_uid", "==", uids[0]))
    assert len(list(rooms.stream(timeout=5))) == 1
