"""ASGI contracts reuse the real SP03 composition and fake Firestore transaction API."""

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sameplace.decor.catalog import preset
from sameplace.social.composition import make_room_router
from test_sameplace_room_storage import Database, transactional


def test_decor_http_authorization_commit_and_realtime_fence():
    db = Database()
    enabled = [True]
    calls = []

    def identify(request: Request):
        uid = request.headers.get("authorization")
        calls.append(uid)
        if uid not in {"owner", "guest", "outsider"}:
            raise HTTPException(401, "AUTH_REQUIRED")
        return {"uid": uid, "platform_owner": uid == "owner"}

    app = FastAPI()
    app.include_router(
        make_room_router(
            identify,
            lambda: (db, transactional),
            lambda: enabled[0],
            lambda: True,
            lambda origin: origin == "https://example.invalid",
        ),
        prefix="/api",
    )
    client = TestClient(app)
    base = "/api/sameplace"
    owner, guest = {"Authorization": "owner"}, {"Authorization": "guest"}

    def post(path, headers=owner, **payload):
        return client.post(
            base + path, headers=headers, json={"request_id": uuid4().hex, **payload}
        )

    assert post("/rooms", slug="friday", name="Friday", capacity=3).status_code == 200
    invite = post("/rooms/friday/invite", version=1, target_kind="uid", target="guest").json()
    assert post("/redeem", guest, token=invite["invitation_token"]).status_code == 200
    path = "/rooms/friday/decor"
    assert client.get(base + path).status_code == 401
    assert client.get(base + path, headers={"Authorization": "outsider"}).status_code == 404
    response = client.get(base + path, headers=guest)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert (
        post(
            path + "/publish",
            guest,
            location="lounge",
            revision=0,
            room_version=3,
            scene=preset("beach"),
        ).status_code
        == 403
    )
    assert post(path + "/music", guest, scope="room", revision=0, action="play").status_code == 403
    bad = post(
        path + "/publish",
        location="lounge",
        revision=0,
        room_version=3,
        scene={"url": "private-marker"},
    )
    assert bad.status_code == 422 and "private-marker" not in bad.text
    ticket = client.post(
        base + "/rooms/friday/ticket", headers=guest, json={"origin": "https://example.invalid"}
    ).json()["ticket"]
    with client.websocket_connect(
        base + "/realtime", headers={"Origin": "https://example.invalid"}
    ) as socket:
        socket.send_json({"type": "auth", "ticket": ticket})
        first = socket.receive_json()
        assert first["type"] == "room.snapshot"
        changed = post(
            path + "/publish", location="lounge", revision=0, room_version=3, scene=preset("beach")
        )
        assert changed.status_code == 200, changed.text
        second = socket.receive_json()
        assert second["room_revision"] > first["room_revision"]
        assert (
            client.get(base + path, headers=guest).json()["scenes"]["lounge"]["scene"]["background"]
            == "beach"
        )
    count = len(calls)
    enabled[0] = False
    assert client.get(base + path, headers=owner).status_code == 404
    assert len(calls) == count
