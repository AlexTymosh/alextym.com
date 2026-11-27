"""Real ASGI HTTP/WS transport over synthetic identity and Firestore transaction adapter."""

from uuid import uuid4
from copy import deepcopy
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sameplace.social.composition import make_room_router
from test_sameplace_room_storage import Database, transactional

BASE = "/api/sameplace"
ORIGIN = "https://example.invalid"
OWNER = {"Authorization": "owner"}
GUEST = {"Authorization": "guest"}


def key(**kwargs):
    return {"request_id": uuid4().hex, **kwargs}


@pytest.fixture
def transport():
    db = Database()
    state = {"enabled": True, "realtime": True, "denied": set(), "calls": 0}

    def identify(request: Request):
        token = request.headers.get("authorization")
        state["calls"] += 1
        if token not in {"owner", "guest", "outsider"} or token in state["denied"]:
            raise HTTPException(401, "AUTH_REQUIRED")
        return {"uid": token, "platform_owner": token == "owner"}

    app = FastAPI()
    app.include_router(
        make_room_router(
            identify,
            lambda: (db, transactional),
            lambda: state["enabled"],
            lambda: state["realtime"],
            lambda origin: origin == ORIGIN,
        ),
        prefix="/api",
    )
    client = TestClient(app)
    response = client.post(
        BASE + "/rooms", headers=OWNER, json=key(slug="friday", name="Room", capacity=2)
    )
    assert response.status_code == 200, response.text
    invitation = client.post(
        BASE + "/rooms/friday/invite",
        headers=OWNER,
        json=key(version=1, target_kind="uid", target="guest"),
    )
    assert invitation.status_code == 200, invitation.text
    response = client.post(
        BASE + "/redeem", headers=GUEST, json=key(token=invitation.json()["invitation_token"])
    )
    assert response.status_code == 200, response.text
    return client, db, state


def ticket(client, headers=OWNER):
    response = client.post(BASE + "/rooms/friday/ticket", headers=headers, json={"origin": ORIGIN})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"ticket", "protocol_version"}
    return response.json()["ticket"]


def handshake(socket, secret):
    socket.send_json({"type": "auth", "ticket": secret})
    return socket.receive_json()


def test_disabled_and_unauthorized_routes_have_no_private_data(transport):
    client, db, state = transport
    before = deepcopy(db.records)
    state["enabled"] = False
    calls = state["calls"]
    assert client.get(BASE + "/social/me", headers=OWNER).status_code == 404
    assert (
        client.post(BASE + "/rooms/friday/ticket", headers=OWNER, content=b"bad").status_code == 404
    )
    assert state["calls"] == calls
    state["enabled"] = True
    assert client.get(BASE + "/social/me").status_code == 401
    assert (
        client.get(BASE + "/rooms/friday/chat", headers={"Authorization": "outsider"}).status_code
        == 404
    )
    assert (
        client.post(
            BASE + "/rooms/friday/ticket",
            headers={"Authorization": "outsider"},
            json={"origin": ORIGIN},
        ).status_code
        == 404
    )
    assert (
        client.post(
            BASE + "/rooms/friday/ticket", headers=OWNER, json={"origin": "https://other.invalid"}
        ).status_code
        == 403
    )
    state["realtime"] = False
    response = client.post(BASE + "/rooms/friday/ticket", headers=OWNER, json={"origin": ORIGIN})
    assert response.status_code == 503 and response.json()["detail"] == "REALTIME_DISABLED"
    assert db.records == before


def test_websocket_lease_ping_and_single_use(transport):
    client, db, state = transport
    token = ticket(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            BASE + "/realtime", headers={"Origin": "https://evil.invalid"}
        ):
            pass
    with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as ws:
        snapshot = handshake(ws, token)
        assert snapshot["type"] == "room.snapshot"
        assert len(snapshot["people"]) == 1 and snapshot["people"][0]["self"] is True
        before = deepcopy(db.records)
        calls = state["calls"]
        for _ in range(3):
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}
        assert before == db.records and calls == state["calls"]
    with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as ws:
        assert handshake(ws, token) == {"type": "error", "code": "TICKET_INVALID"}


def test_identity_rechecked_after_ticket(transport):
    client, _, state = transport
    secret = ticket(client, GUEST)
    state["denied"].add("guest")
    with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as ws:
        assert handshake(ws, secret) == {"type": "error", "code": "AUTH_REQUIRED"}


def test_revoke_live_room_membership_via_real_core_command(transport):
    client, _, _ = transport
    secret = ticket(client, GUEST)
    with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as ws:
        snapshot = handshake(ws, secret)
        assert snapshot["type"] == "room.snapshot"
        room = client.get(BASE + "/rooms/friday", headers=OWNER).json()
        result = client.post(
            BASE + "/rooms/friday/block",
            headers=OWNER,
            json=key(version=room["version"], uid="guest"),
        )
        assert result.status_code == 200, result.text
        assert ws.receive_json() == {"type": "error", "code": "REALTIME_REVOKED"}
        assert client.get(BASE + "/rooms/friday/chat", headers=GUEST).status_code == 404


def test_chat_commit_notification_and_invalid_text(transport):
    client, _, _ = transport
    with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as ws:
        initial = handshake(ws, ticket(client))
        response = client.post(
            BASE + "/rooms/friday/chat/send", headers=OWNER, json=key(text="<b>plain</b>")
        )
        assert response.status_code == 200, response.text
        latest = ws.receive_json()
        assert (
            latest["sequence"] > initial["sequence"]
            and latest["chat_revision"] > initial["chat_revision"]
        )
        assert "plain" not in str(latest)
        assert (
            client.get(BASE + "/rooms/friday/chat", headers=GUEST).json()["messages"][0]["text"]
            == "<b>plain</b>"
        )
        response = client.post(
            BASE + "/rooms/friday/chat/send", headers=OWNER, json=key(text="synthetic-secret\u0000")
        )
        assert response.status_code == 422 and "synthetic-secret" not in response.text


def test_quota_cooldown_shares_core_and_social_router(transport):
    client, db, state = transport

    class ResourceExhausted(Exception):
        pass

    def fail(*args, **kwargs):
        raise ResourceExhausted()

    db.collection = fail
    assert client.get(BASE + "/rooms/friday/chat", headers=OWNER).status_code == 503
    calls = state["calls"]
    response = client.get(BASE + "/rooms", headers=OWNER)
    assert response.status_code == 503 and response.headers.get("Retry-After")
    assert state["calls"] == calls
