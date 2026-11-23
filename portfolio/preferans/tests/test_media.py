"""PR8: seat-bound signalling and the unanimous recording consent state machine."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from preferans.online.media import MediaRooms, SIGNAL_LIFETIME_MS
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def setup():
    db = FakeDB()
    fs = SimpleNamespace(transactional=transactional)
    rooms = FirestoreRooms(db, firestore_module=fs)
    rid = rooms.create("a", "create-media-aa1")["room_id"]
    rooms.join(rid, "b", "join-media-b1", 0)
    rooms.join(rid, "c", "join-media-c1", 1)
    clock = [1_000_000]
    media = MediaRooms(db, firestore_module=fs, now_ms=lambda: clock[0])
    return db, media, rid, clock


def do(media, rid, uid, action, args=None, token=None):
    return media.command(rid, uid, token or f"{uid}-{action}-0001", action, args or {})


def connect_all(media, rid):
    for uid in "abc":
        do(media, rid, uid, "presence", {"audio": True, "video": False})


def test_only_seated_members_can_read_and_signal():
    _, media, rid, _ = setup()
    with pytest.raises(StoreError) as denied:
        media.view(rid, "not-seated")
    assert denied.value.code == 404
    with pytest.raises(StoreError) as denied:
        do(media, rid, "not-seated", "presence", {"audio": True, "video": True})
    assert denied.value.code == 404
    assert media.view(rid, "a")["seat"] == 0
    assert media.view(rid, "a")["participants"] == [
        {"audio": False, "video": False} for _ in range(3)
    ]


def test_offer_is_only_visible_to_receiver_and_expires():
    db, media, rid, clock = setup()
    connect_all(media, rid)
    offer = {"type": "offer", "sdp": "v=0\\r\\n"}
    response = do(
        media, rid, "a", "signal", {"to": 1, "kind": "offer", "data": offer}, "offer-0001"
    )
    assert response["ok"]
    assert media.view(rid, "b")["signals"] == [
        {"sequence": response["version"], "from": 0, "kind": "offer", "data": offer}
    ]
    assert media.view(rid, "a")["signals"] == []
    assert media.view(rid, "c")["signals"] == []
    assert media.view(rid, "b", cursor=response["version"])["signals"] == []
    # No game state or private hand is exposed in the media document.
    assert "hands" not in str(db.docs[f"preferans_rooms/{rid}/media/current"])
    clock[0] += SIGNAL_LIFETIME_MS + 1
    assert media.view(rid, "b")["signals"] == []


def test_idempotency_and_reused_key_conflict():
    _, media, rid, _ = setup()
    connect_all(media, rid)
    args = {"to": 1, "kind": "restart", "data": {}}
    a = do(media, rid, "a", "signal", args, "same-message-0001")
    b = do(media, rid, "a", "signal", args, "same-message-0001")
    assert a == b
    with pytest.raises(StoreError) as ex:
        do(media, rid, "a", "signal", {"to": 2, "kind": "restart", "data": {}}, "same-message-0001")
    assert ex.value.code == 409


def test_recording_requires_three_explicit_votes_and_initiator():
    _, media, rid, _ = setup()
    connect_all(media, rid)
    do(media, rid, "a", "record_request")
    state = media.view(rid, "a")["recording"]
    assert state["votes"] == [True, None, None]
    assert state["status"] == "requested"
    with pytest.raises(StoreError) as ex:
        do(media, rid, "a", "record_start")
    assert ex.value.code == 409
    do(media, rid, "b", "record_vote", {"approve": True})
    assert media.view(rid, "b")["recording"]["status"] == "requested"
    do(media, rid, "c", "record_vote", {"approve": True})
    assert media.view(rid, "c")["recording"]["status"] == "ready"
    with pytest.raises(StoreError) as ex:
        do(media, rid, "b", "record_start")
    assert ex.value.code == 409
    do(media, rid, "a", "record_start")
    assert media.view(rid, "b")["recording"]["status"] == "active"
    do(media, rid, "c", "record_stop")
    stopped = media.view(rid, "a")["recording"]
    assert stopped["status"] == "stopped" and stopped["votes"] == [True, True, False]


def test_deny_vote_and_disconnect_stop_recording():
    _, media, rid, _ = setup()
    connect_all(media, rid)
    do(media, rid, "a", "record_request")
    do(media, rid, "b", "record_vote", {"approve": False})
    assert media.view(rid, "a")["recording"]["status"] == "stopped"
    # Fresh consent required for a new session.
    do(media, rid, "c", "record_request")
    do(media, rid, "a", "record_vote", {"approve": True})
    do(media, rid, "b", "record_vote", {"approve": True}, "b-vote-0002")
    do(media, rid, "c", "record_start")
    do(media, rid, "b", "presence", {"audio": False, "video": False}, "b-offline-0002")
    assert media.view(rid, "c")["recording"]["status"] == "stopped"


def test_reject_signal_abuse_and_stale_participants():
    _, media, rid, clock = setup()
    with pytest.raises(StoreError) as ex:
        do(media, rid, "a", "signal", {"to": 1, "kind": "ice", "data": {"candidate": "hi"}})
    assert ex.value.code == 409
    connect_all(media, rid)
    for args in [
        {"to": 0, "kind": "restart", "data": {}},
        {"to": 2, "kind": "offer", "data": {"type": "answer", "sdp": "hi"}},
        {"to": 1, "kind": "ice", "data": {"candidate": "x" * 2100}},
        {"to": 1, "kind": "restart", "data": {"surprise": "value"}},
    ]:
        with pytest.raises(StoreError) as ex:
            do(media, rid, "a", "signal", args, "invalid-signal" + str(len(args["data"])))
        assert ex.value.code in {409, 413, 422}
    clock[0] += 46_000
    assert media.view(rid, "a")["participants"] == [
        {"audio": False, "video": False} for _ in range(3)
    ]
    with pytest.raises(StoreError):
        do(media, rid, "a", "record_request")
