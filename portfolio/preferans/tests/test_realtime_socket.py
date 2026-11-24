"""ASGI transport contract with a deliberately stubbed authorized storage adapter."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from preferans.online import realtime_api
from preferans.online.realtime import RealtimeHub, now_ms

ROOM = "a" * 32
ORIGIN = "https://example.test"
PATH = f"/api/preferans/rooms/{ROOM}/realtime"


@pytest.fixture
def socket_fixture(monkeypatch):
    for key in (
        "PORTFOLIO_LAB_ENABLED",
        "PREFERANS_ROOMS_ENABLED",
        "PREFERANS_REALTIME_ENABLED",
        "PREFERANS_REALTIME_SINGLE_WORKER",
    ):
        monkeypatch.setenv(key, "true")
    monkeypatch.setenv("PREFERANS_REALTIME_ORIGINS", ORIGIN)
    runtime = RealtimeHub()
    monkeypatch.setattr(realtime_api, "hub", runtime)

    class Storage:
        def view(self, room, uid, owner=False, since_version=None):
            if since_version == 0:
                return {"unchanged": True, "room_id": room, "version": 0}
            return {"room_id": room, "version": 0, "status": "lobby", "my_seat": 0, "hand": []}

        def sync_realtime(self, room, uid):
            runtime.handled(room, runtime.generation(room)[0])
            return {"room_id": room, "version": 0, "status": "lobby"}

    monkeypatch.setattr(realtime_api, "_store", Storage)
    allowed = [True]

    def verify(authorization):
        if not allowed[0] or authorization != "credential":
            raise HTTPException(403, "Denied")
        return "uid", False

    app = FastAPI()
    app.include_router(realtime_api.make_realtime_router(verify), prefix="/api")
    return TestClient(app), runtime, allowed


def auth(ws, token):
    ws.send_json({"type": "authenticate", "protocol": 1, "ticket": token})


def issue(runtime):
    return runtime.issue(ROOM, "uid", 0, ORIGIN, "credential", now_ms())


def test_socket_origin_and_ticket_replay(socket_fixture):
    client, runtime, _ = socket_fixture
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(PATH, headers={"origin": "https://evil.test"}),
    ):
        pass
    token = issue(runtime)
    with client.websocket_connect(PATH, headers={"origin": ORIGIN}) as ws:
        auth(ws, token)
        frame = ws.receive_json()
        assert frame["type"] == "snapshot"
        assert frame["view"]["my_seat"] == 0
        assert "credential" not in str(frame)
        ws.send_json({"type": "ping", "protocol": 1})
        assert ws.receive_json()["type"] == "pong"
    with client.websocket_connect(PATH, headers={"origin": ORIGIN}) as ws:
        auth(ws, token)
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_revoked_credential_rejected_before_projection(socket_fixture):
    client, runtime, allowed = socket_fixture
    token = issue(runtime)
    allowed[0] = False
    with client.websocket_connect(PATH, headers={"origin": ORIGIN}) as ws:
        auth(ws, token)
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 4403
