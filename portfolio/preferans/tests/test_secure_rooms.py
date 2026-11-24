from __future__ import annotations

import copy
import inspect
from types import SimpleNamespace

import pytest
from google.api_core.exceptions import AlreadyExists
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1 import Client

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

    def get(self, transaction=None, timeout=None):
        if transaction is not None:
            return transaction.read_document(self)
        return FakeSnapshot(self.db.docs.get(self.path))


class FakeCollection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, key):
        return FakeDocument(self.db, self.path + "/" + key)

    def order_by(self, field, direction=None):
        self.sort_field = field
        self.descending = direction == "DESCENDING"
        return self

    def limit(self, count):
        self.count = count
        return self

    def stream(self, timeout=None):
        prefix = self.path + "/"
        rows = [
            (k, v)
            for k, v in self.db.docs.items()
            if k.startswith(prefix) and "/" not in k[len(prefix) :] and self.sort_field in v
        ]
        rows.sort(key=lambda pair: pair[1][self.sort_field], reverse=self.descending)
        return iter(FakeSnapshot(v) for _, v in rows[: self.count])


class FakeTransaction:
    def __init__(self, db):
        self.db = db
        self.pending = []

    def get(self, ref):
        # The Python SDK yields snapshots even for one DocumentReference.
        yield self.read_document(ref)

    def read_document(self, ref):
        if self.pending:
            raise ValueError("Attempted read after write in a transaction")
        return FakeSnapshot(self.db.docs.get(ref.path))

    def create(self, ref, value):
        self.pending.append(("create", ref.path, copy.deepcopy(value)))

    def set(self, ref, value):
        self.pending.append(("set", ref.path, copy.deepcopy(value)))

    def commit(self):
        # Preconditions are checked at commit, and a failed batch writes nothing.
        updated = copy.deepcopy(self.db.docs)
        for kind, path, value in self.pending:
            if kind == "create" and path in updated:
                raise AlreadyExists("Document already exists")
            updated[path] = copy.deepcopy(value)
        self.db.docs = updated


class FakeDB:
    def __init__(self):
        self.docs = {}

    def collection(self, name):
        return FakeCollection(self, name)

    def transaction(self):
        return FakeTransaction(self)


def transactional(function):
    def run(tx):
        try:
            result = function(tx)
            tx.commit()
            return result
        finally:
            tx.pending.clear()

    return run


@pytest.fixture
def service():
    return FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))


def test_fake_matches_sdk_single_document_read_shapes():
    db = FakeDB()
    ref = db.collection("items").document("missing")
    tx = db.transaction()
    assert inspect.isgenerator(tx.get(ref))
    assert next(tx.get(ref)).exists is False
    assert ref.get(transaction=tx).exists is False
    # No RPC is made: Transaction.get returns the lazy generator immediately.
    client = Client(project="demo-preferans-contract", credentials=AnonymousCredentials())
    try:
        assert inspect.isgenerator(client.transaction().get(client.document("items/missing")))
    finally:
        client.close()


def test_fake_rejects_reads_after_writes_and_rolls_back_duplicate_create():
    db = FakeDB()
    existing = db.collection("items").document("existing")
    new = db.collection("items").document("new")
    db.docs[existing.path] = {"value": "original"}
    tx = db.transaction()
    tx.create(new, {"value": "pending"})
    with pytest.raises(ValueError, match="read after write"):
        new.get(transaction=tx)
    with pytest.raises(ValueError, match="read after write"):
        next(tx.get(new))
    tx.create(existing, {"value": "replacement"})
    with pytest.raises(AlreadyExists):
        tx.commit()
    assert db.docs == {existing.path: {"value": "original"}}


def test_fake_query_ignores_subcollections_and_missing_order_field():
    db = FakeDB()
    db.docs = {
        "items/a": {"sequence": 1},
        "items/b": {"sequence": 2},
        "items/missing": {},
        "items/a/children/hidden": {"sequence": 3},
    }
    rows = db.collection("items").order_by("sequence", direction="DESCENDING").limit(10)
    assert [row.to_dict() for row in rows.stream()] == [
        {"sequence": 2},
        {"sequence": 1},
    ]


def test_empty_history_and_rankings(service):
    assert service.history("member") == {"results": [], "has_more": False, "limit": 50}
    assert service.rankings("member") == {"rankings": [], "total_players": 0}


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
            room,
            "p1",
            "badcmd-001",
            3,
            "play",
            {"owner": 0, "card": {"suit": "H", "rank": 7}},
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
