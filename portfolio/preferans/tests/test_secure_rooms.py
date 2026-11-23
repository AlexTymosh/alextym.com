from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from preferans.domain.cards import FULL_DECK, deal
from preferans.domain.game import start_game
from preferans.domain.ledger import ScoreState
from preferans.online.codec import decode, encode
from preferans.online.store import FirestoreRooms, StoreError
from preferans.online.views import seat_view


class FakeSnapshot:
    def __init__(self, payload):
        self.exists = payload is not None
        self.value = copy.deepcopy(payload)

    def to_dict(self):
        return copy.deepcopy(self.value)


class FakeDocument:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def collection(self, name):
        return FakeCollection(self.db, self.path + "/" + name)

    def get(self, timeout=None):
        return FakeSnapshot(self.db.docs.get(self.path))


class FakeCollection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, key):
        return FakeDocument(self.db, self.path + "/" + key)

    def order_by(self, field, direction=None):
        self.sort_field = field
        return self

    def limit(self, count):
        self.count = count
        return self

    def stream(self, timeout=None):
        rows = [(k, v) for k, v in self.db.docs.items() if k.startswith(self.path + "/")]
        rows.sort(key=lambda pair: pair[1][self.sort_field], reverse=True)
        return iter(FakeSnapshot(v) for _, v in rows[: self.count])


class FakeTransaction:
    def __init__(self, db):
        self.db = db
        self.pending = []

    def get(self, ref):
        return FakeSnapshot(self.db.docs.get(ref.path))

    def create(self, ref, value):
        assert ref.path not in self.db.docs
        self.pending.append((ref.path, value))

    def set(self, ref, value):
        self.pending.append((ref.path, value))

    def commit(self):
        for path, value in self.pending:
            self.db.docs[path] = copy.deepcopy(value)


class FakeDB:
    def __init__(self):
        self.docs = {}

    def collection(self, name):
        return FakeCollection(self, name)

    def transaction(self):
        return FakeTransaction(self)


def transactional(function):
    def run(tx):
        result = function(tx)
        tx.commit()
        return result

    return run


@pytest.fixture
def service():
    return FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))


def test_secret_state_codec_roundtrip_and_reject_unknown_types():
    original = start_game(deal(FULL_DECK, 2))
    assert decode(encode(original)) == original
    assert decode(encode(ScoreState.new())) == ScoreState.new()
    with pytest.raises(ValueError):
        decode({"$type": "__import__", "fields": {}})
    with pytest.raises(ValueError):
        decode({"$type": "GameState", "fields": {"hands": []}})


def test_room_lifecycle_private_hands_and_idempotency(service):
    a = service.create("uidA", "create-aa-0001")
    assert service.create("uidA", "create-aa-0001") == a
    room = a["room_id"]
    with pytest.raises(StoreError) as exc:
        service.view(room, "unknown")
    assert exc.value.code == 404
    b = service.join(room, "uidB", "join-bb-0001", 0)
    assert b["version"] == 1
    assert service.join(room, "uidB", "join-bb-0001", 0) == b
    with pytest.raises(StoreError) as exc:
        service.join(room, "uidC", "join-cc-0001", 0)
    assert exc.value.code == 409
    c = service.join(room, "uidC", "join-cc-0001", 1)
    assert c["version"] == 2
    with pytest.raises(StoreError) as exc:
        service.start(room, "uidB", "start-bb-0001", 2, owner=False)
    assert exc.value.code == 403
    start = service.start(room, "uidA", "start-aa-0001", 2, owner=False)
    assert service.start(room, "uidA", "start-aa-0001", 2, owner=False) == start
    assert start["version"] == 3
    first = service.view(room, "uidA")
    other = service.view(room, "uidB")
    assert first["my_seat"] == 0 and other["my_seat"] == 1
    assert first["hand"] != other["hand"]
    assert "discarded" not in first and "widow" in first and not first["widow"]
    assert "uidA" not in str(other) and "uidB" not in str(first)
    assert len(first["hand"]) == 10 and len(other["hand"]) == 10
    assert first["phase"] == "auction"
    # The room version is a compare-and-swap guard for every gameplay action.
    with pytest.raises(StoreError) as exc:
        service.command(room, "uidA", "bid-aa-0001", 2, "pass", {})
    assert exc.value.code == 409
    bid = {"kind": "regular", "level": 6, "suit": "S"}
    event = service.command(room, "uidA", "bid-aa-0001", 3, "bid", {"bid": bid})
    assert service.command(room, "uidA", "bid-aa-0001", 3, "bid", {"bid": bid}) == event
    with pytest.raises(StoreError) as exc:
        service.command(room, "uidA", "bid-aa-0001", 3, "pass", {})
    assert exc.value.code == 409
    for uid, ver in [("uidB", 4), ("uidC", 5)]:
        service.command(room, uid, f"pass-{uid}-0001", ver, "pass", {})
    state = service.view(room, "uidA")
    assert state["phase"] == "discard"
    hidden = service.view(room, "uidB")
    assert hidden["widow"] == state["widow"]
    own = state["hand"][0]
    widow = state["widow"][0]
    service.command(room, "uidA", "discard-aa-0001", 6, "discard", {"cards": [own, widow]})
    history = service.events(room, "uidB")
    last = history["events"][0]
    assert last["action"] == "discard" and last["data"] == {}
    assert own not in last["data"].values()
    assert all(
        "hands" not in str(event) and "discarded" not in str(event) for event in history["events"]
    )
    with pytest.raises(StoreError):
        service.join(room, "uidD", "join-dd-0001", 7)


def test_room_admin_cannot_read_opponent_private_hand(service):
    room = service.create("ownerAdmin", "create-0001")["room_id"]
    service.join(room, "p2", "join-0002", 0)
    service.join(room, "p3", "join-0003", 1)
    service.start(room, "ownerAdmin", "start-0004", 2, owner=False)
    v = service.view(room, "ownerAdmin", owner=True)
    assert "hand" in v and len(v["hand"]) == 10
    # Global Owner not seated can inspect public state, but not other users' cards.
    v2 = service.view(room, "platform-owner", owner=True)
    assert "hand" not in v2 and "legal_cards" not in v2
    assert "game" not in v2


def test_invalid_commands_cannot_mutate_persisted_state(service):
    room = service.create("p1", "create-0001")["room_id"]
    service.join(room, "p2", "join-0002", 0)
    service.join(room, "p3", "join-0003", 1)
    service.start(room, "p1", "start-0004", 2, owner=False)
    view_before = service.view(room, "p1")
    with pytest.raises(StoreError) as exc:
        service.command(
            room, "p1", "badcmd-001", 3, "play", {"owner": 0, "card": {"suit": "H", "rank": 7}}
        )
    assert exc.value.code == 422
    assert service.view(room, "p1") == view_before


def test_views_expose_only_owned_or_revealed_hands():
    game = start_game(deal(FULL_DECK, 2))
    room = {
        "id": "a" * 32,
        "status": "playing",
        "seats": ["A", "B", "C"],
        "game_id": "game",
        "admin_uid": "A",
    }
    view = seat_view(room, game, ScoreState.new(), "B", 3)
    assert view["hand"] == [{"suit": c.suit.value, "rank": c.rank.value} for c in game.hands[1]]
    assert all("cards" not in row for row in view.get("open_hands", []))
    assert "discarded" not in view and "hands" not in view


def test_version_poll_returns_only_unchanged_marker(service):
    room = service.create("member", "create-0001")["room_id"]
    result = service.view(room, "member", since_version=0)
    assert result == {"room_id": room, "version": 0, "unchanged": True}
    with pytest.raises(StoreError) as exc:
        service.view(room, "outsider", since_version=0)
    assert exc.value.code == 404


def test_broken_private_version_fails_closed(service):
    room = service.create("member", "create-0001")["room_id"]
    key = f"preferans_rooms/{room}/private/current"
    service.db.docs[key]["version"] = 999
    with pytest.raises(StoreError) as exc:
        service.view(room, "member")
    assert exc.value.code == 409


def test_invalid_or_foreign_room_id_is_not_disclosed(service):
    for room in ["../../secrets", "", "0123456789", "x" * 32]:
        with pytest.raises(StoreError) as exc:
            service.view(room, "member")
        assert exc.value.code == 404
