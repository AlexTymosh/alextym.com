"""ASGI WebSocket integration using the existing synthetic identity and store."""

from copy import deepcopy
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from sameplace.social.composition import make_room_router
from test_sameplace_room_storage import Database, transactional

BASE = "/api/sameplace"
ORIGIN = "https://example.invalid"


def test_addressed_media_frames_share_room_socket_without_storage_writes():
    db = Database()
    enabled = {"media": True}

    def identify(request: Request):
        uid = request.headers.get("authorization")
        if uid not in ("a", "b", "c"):
            raise HTTPException(401, "AUTH_REQUIRED")
        return {"uid": uid, "platform_owner": uid == "a"}

    app = FastAPI()
    app.include_router(
        make_room_router(
            identify,
            lambda: (db, transactional),
            lambda: True,
            lambda: True,
            lambda origin: origin == ORIGIN,
            media_enabled=lambda: enabled["media"],
            ice_servers=lambda: [],
        ),
        prefix="/api",
    )
    client = TestClient(app)

    def post(path, uid, **payload):
        response = client.post(
            BASE + path, headers={"Authorization": uid}, json={"request_id": uuid4().hex, **payload}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def ticket(uid):
        response = client.post(
            BASE + "/rooms/friday/ticket", headers={"Authorization": uid}, json={"origin": ORIGIN}
        )
        assert response.status_code == 200
        return response.json()["ticket"]

    def get_frame(ws, kind, predicate=lambda value: True):
        for _ in range(15):
            frame = ws.receive_json()
            if frame["type"] == kind and predicate(frame):
                return frame
        raise AssertionError(f"No {kind} frame")

    post("/rooms", "a", slug="friday", name="Media test", capacity=3)
    invitation = post("/rooms/friday/invite", "a", version=1, target_kind="uid", target="b")
    redeemed = post("/redeem", "b", token=invitation["invitation_token"])
    invite_c = post(
        "/rooms/friday/invite", "a", version=redeemed["version"], target_kind="uid", target="c"
    )
    post("/redeem", "c", token=invite_c["invitation_token"])
    with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as a:
        a.send_json({"type": "auth", "ticket": ticket("a")})
        get_frame(a, "room.snapshot")
        get_frame(a, "media.state")
        a.send_json({"type": "media.join"})
        get_frame(a, "media.state", lambda v: v["joined"])
        with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as b:
            b.send_json({"type": "auth", "ticket": ticket("b")})
            get_frame(b, "room.snapshot")
            get_frame(b, "media.state")
            b.send_json({"type": "media.join"})
            other = get_frame(b, "media.state", lambda v: v["joined"] and len(v["peers"]) == 1)[
                "peers"
            ][0]
            peer = get_frame(a, "media.state", lambda v: len(v["peers"]) == 1)["peers"][0]
            assert peer["pair"] == other["pair"]
            with client.websocket_connect(BASE + "/realtime", headers={"Origin": ORIGIN}) as c:
                c.send_json({"type": "auth", "ticket": ticket("c")})
                assert get_frame(c, "error")["code"] == "WAIT_CAPACITY"
            before = deepcopy(db.records)
            sdp = "v=0\r\n" + "x" * 3000
            a.send_json(
                {
                    "type": "media.signal",
                    "target": peer["id"],
                    "pair": peer["pair"],
                    "signal": {"kind": "offer", "sdp": sdp},
                }
            )
            assert get_frame(b, "media.signal")["signal"]["sdp"] == sdp
            assert db.records == before
            b.send_json({"type": "media.mode", "mode": "location"})
            assert get_frame(b, "media.error")["code"] == "MEDIA_DENIED"
            a.send_json({"type": "media.mode", "mode": "location"})
            assert (
                get_frame(b, "media.state", lambda v: v["mode"] == "location")["mode"] == "location"
            )
            enabled["media"] = False
            assert get_frame(b, "media.disabled") == {"type": "media.disabled"}
            b.send_json({"type": "ping"})
            assert get_frame(b, "pong") == {"type": "pong"}
