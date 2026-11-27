from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sameplace.rooms.api import make_room_router
from test_sameplace_room_storage import Database, transactional


@pytest.fixture
def room_client():
    db = Database()

    def identify(request: Request):
        token = request.headers.get("authorization")
        if token not in {"owner", "guest"}:
            raise HTTPException(401, "AUTH_REQUIRED")
        return {"uid": token, "platform_owner": token == "owner"}

    app = FastAPI()
    app.include_router(make_room_router(identify, lambda: (db, transactional)), prefix="/api")
    return TestClient(app), db


def test_actual_http_contract(room_client):
    client, db = room_client
    base = "/api/sameplace"
    owner = {"Authorization": "owner"}
    guest = {"Authorization": "guest"}
    body = {"request_id": uuid4().hex, "slug": "friday", "name": "Room", "capacity": 3}
    assert client.post(base + "/rooms", json=body).status_code == 401
    assert db.records == {}
    assert client.post(base + "/rooms", json=body, headers=guest).status_code == 403
    result = client.post(base + "/rooms", json=body, headers=owner)
    assert result.status_code == 200, result.text
    assert result.headers["Cache-Control"] == "no-store"
    assert client.get(base + "/rooms/friday", headers=guest).status_code == 404
    assert client.get(base + "/rooms", headers=guest).json()["rooms"] == []
    invited = client.post(
        base + "/rooms/friday/invite",
        json={"request_id": uuid4().hex, "version": 1, "target_kind": "uid", "target": "guest"},
        headers=owner,
    )
    assert invited.status_code == 200, invited.text
    redeemed = client.post(
        base + "/redeem",
        json={"request_id": uuid4().hex, "token": invited.json()["invitation_token"]},
        headers=guest,
    )
    assert redeemed.status_code == 200, redeemed.text
    assert client.get(base + "/rooms/friday", headers=guest).status_code == 200
    assert (
        client.post(
            base + "/admin/approval",
            json={"request_id": uuid4().hex, "uid": "guest", "approved": True},
            headers=guest,
        ).status_code
        == 403
    )


def test_invalid_request_never_echoes_secret(room_client):
    client, _ = room_client
    response = client.post(
        "/api/sameplace/redeem",
        json={"request_id": uuid4().hex, "token": "synthetic-secret"},
        headers={"Authorization": "guest"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "INVALID_REQUEST"}
    assert "synthetic-secret" not in response.text
    assert (
        client.post(
            "/api/sameplace/redeem",
            content=b"x" * 17000,
            headers={"Authorization": "guest", "Content-Type": "application/json"},
        ).status_code
        == 413
    )
