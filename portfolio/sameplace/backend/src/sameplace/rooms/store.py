"""Transactional storage port. The host injects the existing Firebase Admin client."""

from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from typing import Any, Protocol, TypeVar

T = TypeVar("T")
Record = dict[str, Any]


class UnitOfWork(Protocol):
    def get(self, key: str) -> Record | None: ...
    def set(self, key: str, value: Record) -> None: ...


class Store(Protocol):
    def run(self, operation: Callable[[UnitOfWork], T]) -> T: ...


class BufferedUnit:
    """All SDK reads occur before any transaction write, including on retry."""

    def __init__(self, read: Callable[[str], Record | None]):
        self.read = read
        self.cache: dict[str, Record | None] = {}
        self.writes: dict[str, Record] = {}

    def get(self, key: str) -> Record | None:
        if key in self.writes:
            return deepcopy(self.writes[key])
        if key not in self.cache:
            self.cache[key] = self.read(key)
        return deepcopy(self.cache[key])

    def set(self, key: str, value: Record) -> None:
        self.writes[key] = deepcopy(value)


class FirestoreStore:
    """No Firebase initialization, credentials, or host imports in project code."""

    def __init__(self, database: Any, transactional: Callable):
        self.database = database
        self.transactional = transactional

    def run(self, operation: Callable[[UnitOfWork], T]) -> T:
        collection = self.database.collection("sameplace_room_core_v1")

        def execute(transaction):
            def read(key):
                snap = collection.document(key).get(transaction=transaction, timeout=5.0)
                return snap.to_dict() if snap.exists else None

            unit = BufferedUnit(read)
            result = operation(unit)
            for key, record in unit.writes.items():
                transaction.set(collection.document(key), record)
            return result

        return self.transactional(execute)(self.database.transaction(max_attempts=3))


class MemoryStore:
    """Serializable test double; never selected by a production route."""

    def __init__(self):
        self.records: dict[str, Record] = {}
        self.lock = RLock()

    def run(self, operation: Callable[[UnitOfWork], T]) -> T:
        with self.lock:
            unit = BufferedUnit(self.records.get)
            result = operation(unit)
            self.records.update(unit.writes)
            return deepcopy(result)
