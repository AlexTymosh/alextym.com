from copy import deepcopy
from uuid import uuid4

import pytest
from sameplace.rooms.models import Actor, CreateRoom
from sameplace.rooms.service import RoomService
from sameplace.rooms.store import FirestoreStore


class Snapshot:
    def __init__(self, value):
        self.value = value
        self.exists = value is not None

    def to_dict(self):
        return deepcopy(self.value)


class Ref:
    def __init__(self, key):
        self.key = key

    def get(self, transaction, timeout):
        assert not transaction.writes, "Firestore reads after writes"
        assert timeout == 5.0
        return Snapshot(transaction.database.records.get(self.key))


class Transaction:
    def __init__(self, database):
        self.database = database
        self.writes = {}

    def set(self, ref, data):
        self.writes[ref.key] = deepcopy(data)


class Database:
    def __init__(self):
        self.records = {}

    def collection(self, name):
        assert name == "sameplace_room_core_v1"
        return self

    def document(self, key):
        return Ref(key)

    def transaction(self, max_attempts):
        assert max_attempts == 3
        return Transaction(self)


def transactional(fn):
    def execute(tx):
        result = fn(tx)
        tx.database.records.update(tx.writes)
        return result

    return execute


def test_transaction_adapter_runs_actual_service_and_rolls_back_on_exception():
    db = Database()
    store = FirestoreStore(db, transactional)
    owner = Actor(uid="synthetic", platform_owner=True)
    service = RoomService(store)
    room = service.create(
        owner, CreateRoom(request_id=uuid4().hex, slug="room-one", name="Room", capacity=3)
    )
    assert service.get(owner, "room-one")["id"] == room["id"]
    before = deepcopy(db.records)

    def fail(unit):
        unit.set("unsafe", {"secret": "value"})
        raise RuntimeError("synthetic failure")

    with pytest.raises(RuntimeError):
        store.run(fail)
    assert db.records == before
