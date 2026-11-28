"""Media invariants on the actual single-worker Hub, without external providers."""

from uuid import uuid4

import pytest

from sameplace.media.signaling import MediaState, configured_media_capacity, valid_signal
from sameplace.social.hub import Hub
from sameplace.social.models import Move


@pytest.fixture
def setup():
    hub = Hub()
    media = MediaState(hub, lambda: True, lambda: [])
    connections = {}

    def add(uid, slug="room-one"):
        profile = {
            "public_id": ("a" if uid == "a" else "b" if uid == "b" else "c") * 32,
            "nickname": uid,
            "avatar": "initials",
            "privacy": {"show_online": False, "show_last_seen": False},
        }
        access = {
            "room": {"slug": slug, "id": slug, "status": "active", "capacity": 4},
            "limits": {"active_rooms": 4, "active_participants": 20, "capacity_ceiling": 4},
            "profile": profile,
        }
        ticket = hub.consume(
            hub.issue(uid, slug, "https://example.invalid", "credential"), "https://example.invalid"
        )
        conn = hub.admit(ticket, access, hub.version())
        connections[uid] = conn
        return conn

    add("a")
    add("b")
    return hub, media, connections, add


def join(media, uid, connection):
    return media.command("room-one", uid, connection, {"type": "media.join"})


def view(media, uid, connection):
    return media.state("room-one", uid, connection)[0]


def offer(target, pair):
    return {
        "type": "media.signal",
        "target": target,
        "pair": pair,
        "signal": {"kind": "offer", "sdp": "v=0\r\n"},
    }


def test_signal_is_private_bounded_and_bound_to_pair(setup):
    _, media, conn, add = setup
    add("c", "room-two")
    assert join(media, "a", conn["a"]) is None
    assert join(media, "b", conn["b"]) is None
    a = view(media, "a", conn["a"])
    b = view(media, "b", conn["b"])
    pair = a["peers"][0]["pair"]
    assert b["peers"][0]["pair"] == pair
    assert a["peers"][0]["offerer"] != b["peers"][0]["offerer"]
    assert media.command("room-one", "a", conn["a"], offer("c" * 32, pair)) == "MEDIA_STALE_PEER"
    assert media.command("room-one", "a", conn["a"], offer("b" * 32, pair)) is None
    assert media.state("room-one", "a", conn["a"])[1] == []
    messages = media.state("room-one", "b", conn["b"])[1]
    assert messages == [
        {
            "type": "media.signal",
            "from": "a" * 32,
            "pair": pair,
            "signal": {"kind": "offer", "sdp": "v=0\r\n"},
        }
    ]
    assert media.state("room-one", "b", conn["b"])[1] == []


def test_second_tab_and_reconnect_rotate_pair(setup):
    hub, media, conn, add = setup
    first = conn["a"]
    join(media, "a", first)
    join(media, "b", conn["b"])
    pair = view(media, "a", first)["peers"][0]["pair"]
    second = add("a")
    assert view(media, "a", second)["occupied"]
    assert join(media, "a", second) == "MEDIA_TAB_LIMIT"
    media.disconnect("room-one", "a", first)
    hub.leave("room-one", "a", first)
    assert join(media, "a", second) is None
    assert view(media, "a", second)["peers"][0]["pair"] != pair
    assert media.command("room-one", "a", second, offer("b" * 32, pair)) == "MEDIA_STALE_PEER"


def test_channel_move_prunes_old_queue_and_rotates_pair(setup):
    hub, media, conn, _ = setup
    join(media, "a", conn["a"])
    join(media, "b", conn["b"])
    pair = view(media, "a", conn["a"])["peers"][0]["pair"]
    assert (
        media.command("room-one", "b", conn["b"], {"type": "media.mode", "mode": "location"})
        == "MEDIA_DENIED"
    )
    assert (
        media.command(
            "room-one",
            "a",
            conn["a"],
            {"type": "media.mode", "mode": "location"},
            {"channel": True},
        )
        is None
    )
    assert media.command("room-one", "a", conn["a"], offer("b" * 32, pair)) is None
    hub.move("room-one", "b", Move(request_id=uuid4().hex, location="table"))
    assert view(media, "a", conn["a"])["peers"] == []
    assert media.state("room-one", "b", conn["b"])[1] == []
    hub.move("room-one", "b", Move(request_id=uuid4().hex, location="lounge"))
    assert view(media, "a", conn["a"])["peers"][0]["pair"] != pair


def test_moderation_does_not_remote_unmute(setup):
    _, media, conn, _ = setup
    join(media, "a", conn["a"])
    join(media, "b", conn["b"])
    tracks = {"type": "media.tracks", "microphone": True, "camera": True}
    assert media.command("room-one", "b", conn["b"], tracks) is None
    mute = {"type": "media.mute", "target": "b" * 32, "muted": True}
    assert media.command("room-one", "a", conn["a"], mute) == "MEDIA_DENIED"
    permission = {"moderate": True, "owner": True, "owner_uid": "a"}
    assert media.command("room-one", "a", conn["a"], mute, permission) is None
    assert view(media, "b", conn["b"])["muted"]
    assert not view(media, "a", conn["a"])["peers"][0]["microphone"]
    media.command("room-one", "b", conn["b"], tracks)
    media.command("room-one", "a", conn["a"], {**mute, "muted": False}, permission)
    assert not view(media, "b", conn["b"])["muted"]
    assert not view(media, "a", conn["a"])["peers"][0]["microphone"]
    assert view(media, "a", conn["a"])["peers"][0]["camera"]


def test_revocation_and_disabled_feature_close_media(setup):
    hub, media, conn, _ = setup
    join(media, "a", conn["a"])
    join(media, "b", conn["b"])
    hub.invalidate("room-one", "b")
    assert view(media, "a", conn["a"])["peers"] == []
    assert media.state("room-one", "b", conn["b"]) == (None, [])
    media.enabled = lambda: False
    assert media.state("room-one", "a", conn["a"]) == (None, [])
    assert not media.sessions


def test_queue_bound_and_invalid_payload(setup):
    _, media, conn, _ = setup
    join(media, "a", conn["a"])
    join(media, "b", conn["b"])
    pair = view(media, "a", conn["a"])["peers"][0]["pair"]
    assert not valid_signal({"kind": "offer", "sdp": "x" * 24001})
    assert not valid_signal(
        {"kind": "ice", "candidate": "x", "sdpMid": None, "sdpMLineIndex": True}
    )
    for _ in range(96):
        assert media.command("room-one", "a", conn["a"], offer("b" * 32, pair)) is None
    assert media.command("room-one", "a", conn["a"], offer("b" * 32, pair)) == "MEDIA_BUSY"
    assert len(media.state("room-one", "b", conn["b"])[1]) == 96


def test_room_wide_moves_keep_same_peer_connection(setup):
    hub, media, conn, _ = setup
    join(media, "a", conn["a"])
    join(media, "b", conn["b"])
    pair = view(media, "a", conn["a"])["peers"][0]["pair"]
    hub.move("room-one", "b", Move(request_id=uuid4().hex, location="table"))
    hub.fence("room-one")
    assert view(media, "a", conn["a"])["peers"][0]["pair"] == pair


def test_initial_trial_capacity_is_bounded(monkeypatch, setup):
    monkeypatch.delenv("SAMEPLACE_MEDIA_CAPACITY", raising=False)
    assert configured_media_capacity() == 2
    monkeypatch.setenv("SAMEPLACE_MEDIA_CAPACITY", "999")
    assert configured_media_capacity() == 2
    monkeypatch.setenv("SAMEPLACE_MEDIA_CAPACITY", "bad")
    assert configured_media_capacity() == 2
    monkeypatch.setenv("SAMEPLACE_MEDIA_CAPACITY", "4")
    assert configured_media_capacity() == 4
    _, media, conn, add = setup
    media.capacity = lambda: 2
    add("c")
    assert join(media, "a", conn["a"]) == "MEDIA_CAPACITY"
