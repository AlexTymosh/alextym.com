"""ASGI regression for the actual WebSocket route with an authorized store stub."""

from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from preferans.online import realtime_api, router
from preferans.online.realtime import RealtimeHub, now_ms

ROOM = "b" * 32
ORIGIN = "https://example.test"
PATH = f"/api/preferans/rooms/{ROOM}/realtime"


@pytest.fixture
def service(monkeypatch):
    for key in (
        "PORTFOLIO_LAB_ENABLED",
        "PREFERANS_ROOMS_ENABLED",
        "PREFERANS_REALTIME_ENABLED",
        "PREFERANS_REALTIME_SINGLE_WORKER",
        "PREFERANS_MEDIA_ENABLED",
        "PREFERANS_LIVE_MEDIA_WS_ENABLED",
    ):
        monkeypatch.setenv(key, "true")
    monkeypatch.setenv("PREFERANS_REALTIME_ORIGINS", ORIGIN)
    runtime = RealtimeHub()
    monkeypatch.setattr(realtime_api, "hub", runtime)
    calls = []

    class Storage:
        def view(self, room, uid, owner=False, since_version=None):
            calls.append("view")
            if since_version == 7:
                return {"unchanged": True, "room_id": room, "version": 7}
            return {
                "room_id": room,
                "version": 7,
                "status": "lobby",
                "my_seat": "abc".index(uid),
                "hand": [],
                "occupied": [True] * 3,
            }

        def sync_realtime(self, room, uid):
            calls.append("sync")
            runtime.handled(room, runtime.generation(room)[0])
            return {"room_id": room, "version": 7, "status": "lobby"}

    monkeypatch.setattr(realtime_api, "_store", Storage)

    def verify(authorization):
        if authorization not in ("a", "b", "c"):
            raise HTTPException(403, "Denied")
        return authorization, False

    app = FastAPI()
    app.include_router(realtime_api.make_realtime_router(verify), prefix="/api")
    return TestClient(app), runtime, calls


def send(ws, message_type, **args):
    ws.send_json({"type": message_type, "protocol": 1, **args})


def until(ws, wanted, *, forbid=()):
    for _ in range(16):
        value = ws.receive_json()
        assert value["type"] not in forbid
        if value["type"] == wanted:
            return value
    raise AssertionError(f"Missing frame {wanted}")


def test_relay_uses_existing_socket_without_other_seat_leaks(service):
    client, runtime, calls = service
    with ExitStack() as stack:
        sockets = []
        for i, uid in enumerate("abc"):
            token = runtime.issue(ROOM, uid, i, ORIGIN, uid, now_ms())
            ws = stack.enter_context(client.websocket_connect(PATH, headers={"origin": ORIGIN}))
            send(ws, "authenticate", ticket=token)
            snapshot = until(ws, "snapshot")
            assert snapshot["live_media"] is True
            assert snapshot["view"]["my_seat"] == i
            sockets.append(ws)
        # Explicit opt-in. New participants do not broadcast SDP or acquire devices.
        for i, ws in enumerate(sockets):
            send(ws, "media_join")
            roster = until(ws, "media_state")["participants"]
            assert roster[i]["audio"] is False and roster[i]["video"] is False
        # Wait for the complete roster on the first socket.
        roster = until(sockets[0], "media_state")["participants"]
        while roster[2] is None:
            roster = until(sockets[0], "media_state")["participants"]
        # Existing presence/room sync is now stable. No writes/reads caused by media frames.
        baseline = len(calls)
        send(
            sockets[0],
            "media_signal",
            to=1,
            to_session=roster[1]["session"],
            kind="offer",
            data={"type": "offer", "sdp": "v=0\r\n" + "x" * 2000},
        )
        signal = until(sockets[1], "media_signal")
        assert signal["from"] == 0 and signal["to_session"] == roster[1]["session"]
        assert "connection" not in str(signal)
        send(sockets[2], "ping")
        until(sockets[2], "pong", forbid=("media_signal",))
        send(sockets[0], "media_record_start")
        until(sockets[0], "media_error")
        send(sockets[0], "ping")
        until(sockets[0], "pong", forbid=("media_signal",))
        assert runtime.rooms[ROOM].revision == 7
        assert len(calls) == baseline
        send(sockets[0], "media_leave")
        left = until(sockets[1], "media_state")["participants"]
        while left[0] is not None:
            left = until(sockets[1], "media_state")["participants"]
        assert runtime.rooms[ROOM].revision == 7


def test_legacy_media_is_blocked_in_new_mode(monkeypatch):
    monkeypatch.setenv("PREFERANS_MEDIA_ENABLED", "true")
    monkeypatch.setenv("PREFERANS_LIVE_MEDIA_WS_ENABLED", "true")

    # The route must refuse before any storage adapter or recording mutation.
    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy storage must not be reached")

    monkeypatch.setattr(router, "_context", forbidden)
    with pytest.raises(HTTPException) as exc:
        router.room_media("a" * 32, SimpleNamespace(), cursor=0)
    assert exc.value.status_code == 404
