"""PR9: privacy, retention and room-isolation release regression tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from preferans.online.media import MediaRooms, SIGNAL_LIFETIME_MS
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def fixture_rooms():
    db = FakeDB()
    fs = SimpleNamespace(transactional=transactional)
    rooms = FirestoreRooms(db, firestore_module=fs)
    left = rooms.create("alice", "room-a-create-01")["room_id"]
    rooms.join(left, "bob", "room-a-join-b-01", 0)
    rooms.join(left, "carol", "room-a-join-c-01", 1)
    right = rooms.create("dave", "room-b-create-01")["room_id"]
    rooms.join(right, "erin", "room-b-join-e-01", 0)
    rooms.join(right, "frank", "room-b-join-f-01", 1)
    now = [1_000_000]
    media = MediaRooms(db, firestore_module=fs, now_ms=lambda: now[0])
    return db, media, left, right, now


def act(media, rid, uid, action, args, key):
    return media.command(rid, uid, key, action, args)


def test_media_isolation_even_with_valid_other_room_membership():
    _, media, left, right, _ = fixture_rooms()
    for uid in ("alice", "bob", "carol"):
        act(media, left, uid, "presence", {"audio": True, "video": False}, f"up-{uid}-0001")
    offer = {"type": "offer", "sdp": "v=0\r\na=fingerprint:test\r\n"}
    act(media, left, "alice", "signal", {"to": 1, "kind": "offer", "data": offer}, "left-offer-001")
    assert len(media.view(left, "bob")["signals"]) == 1
    for uid in ("dave", "erin", "frank"):
        with pytest.raises(StoreError) as err:
            media.view(left, uid)
        assert err.value.code == 404
    assert media.view(right, "erin")["signals"] == []
    with pytest.raises(StoreError) as err:
        act(
            media,
            left,
            "dave",
            "signal",
            {"to": 1, "kind": "offer", "data": offer},
            "cross-room-0001",
        )
    assert err.value.code == 404


def test_signals_expire_from_api_and_metadata_retention_is_explicit():
    db, media, rid, _, clock = fixture_rooms()
    for uid in ("alice", "bob", "carol"):
        act(media, rid, uid, "presence", {"audio": True, "video": False}, f"up-{uid}-0002")
    response = act(
        media,
        rid,
        "alice",
        "signal",
        {"to": 1, "kind": "ice", "data": {"candidate": "a=candidate:1"}},
        "ice-00000001",
    )
    assert media.view(rid, "bob", cursor=response["version"] - 1)["signals"]
    clock[0] += SIGNAL_LIFETIME_MS + 1
    assert media.view(rid, "bob")["signals"] == []
    raw = db.docs[f"preferans_rooms/{rid}/preferans_media/current"]
    assert "expires_at" in raw
    assert "game" not in raw and "score" not in raw and "hands" not in str(raw)
    assert "preferans_rooms" in next(iter(db.docs))
    operations = [v for k, v in db.docs.items() if "/preferans_media_ops/" in k]
    assert len(operations) == 1
    assert set(operations[0]) == {"fingerprint", "response", "expires_at"}
    assert "candidate" not in str(operations[0])


def test_invalid_media_payloads_fail_before_any_state_write():
    db, media, rid, _, _ = fixture_rooms()
    act(media, rid, "alice", "presence", {"audio": True, "video": False}, "alice-present-01")
    initial = media.view(rid, "alice")["version"]
    for idx, (action, args) in enumerate(
        (
            ("signal", {"to": 2, "kind": "offer", "data": {"type": "offer", "sdp": "s" * 5900}}),
            ("signal", {"to": 2, "kind": "ice", "data": {"candidate": "x" * 2050}}),
            ("signal", {"to": 0, "kind": "restart", "data": {}}),
            ("record_vote", {"approve": "yes"}),
        )
    ):
        with pytest.raises(StoreError) as err:
            act(media, rid, "alice", action, args, f"bad-media-{idx}-key")
        assert err.value.code in {409, 413, 422}
    assert media.view(rid, "alice")["version"] == initial
    assert not [k for k in db.docs if "/preferans_media_ops/" in k]


def test_stale_active_recording_never_survives_projection():
    _, media, rid, _, clock = fixture_rooms()
    for uid in ("alice", "bob", "carol"):
        act(media, rid, uid, "presence", {"audio": True, "video": False}, f"record-{uid}-up01")
    act(media, rid, "alice", "record_request", {}, "new-record-req1")
    act(media, rid, "bob", "record_vote", {"approve": True}, "new-record-b-01")
    act(media, rid, "carol", "record_vote", {"approve": True}, "new-record-c-01")
    act(media, rid, "alice", "record_start", {}, "new-record-go01")
    assert media.view(rid, "alice")["recording"]["status"] == "active"
    clock[0] += 46_000
    assert media.view(rid, "alice")["recording"]["status"] == "stopped"
    # Stale state cannot become active merely because one person returns.
    act(media, rid, "alice", "presence", {"audio": True, "video": False}, "rejoin-alice-01")
    assert media.view(rid, "alice")["recording"]["status"] == "stopped"
