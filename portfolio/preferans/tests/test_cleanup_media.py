"""Release-maintenance safety checks using a fake, bounded Firestore surface."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path


_script = Path(__file__).resolve().parents[1] / "backend" / "scripts" / "cleanup_media.py"
spec = importlib.util.spec_from_file_location("preferans_cleanup_media", _script)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Snapshot:
    def __init__(self, ref, data):
        self.reference = ref
        self.data = data
        self.exists = data is not None
        self.update_time = datetime(2026, 11, 20, tzinfo=UTC)

    def to_dict(self):
        return self.data


class Document:
    def __init__(self, state, path):
        self.state, self.path = state, path

    def get(self, timeout=None):
        return Snapshot(self, self.state.get(self.path))

    def collection(self, name):
        return Collection(self.state, self.path + "/" + name)

    def delete(self, option=None, timeout=None):
        assert option == ("guard", datetime(2026, 11, 20, tzinfo=UTC))
        self.state.pop(self.path, None)


class Collection:
    def __init__(self, state, path):
        self.state, self.path = state, path
        self.limit_count = 100

    def document(self, doc):
        return Document(self.state, self.path + "/" + doc)

    def limit(self, count):
        self.limit_count = count
        return self

    def stream(self, timeout=None):
        prefix = self.path + "/"
        docs = sorted(
            path
            for path in self.state
            if path.startswith(prefix) and "/" not in path[len(prefix) :]
        )
        return iter(
            Snapshot(Document(self.state, path), self.state[path])
            for path in docs[: self.limit_count]
        )


class DB:
    def __init__(self, state):
        self.state = state

    def collection(self, name):
        return Collection(self.state, name)

    def write_option(self, *, last_update_time):
        return ("guard", last_update_time)


def test_maintenance_is_dry_run_by_default_and_bounded():
    now = datetime(2026, 11, 23, tzinfo=UTC)
    state = {
        "preferans_rooms/room-a": {"status": "closed"},
        "preferans_rooms/room-b": {"status": "closed"},
        "preferans_rooms/room-a/preferans_media/current": {
            "expires_at": now - timedelta(minutes=5)
        },
        "preferans_rooms/room-a/preferans_media_ops/one": {"expires_at": now - timedelta(hours=1)},
        "preferans_rooms/room-a/preferans_media_ops/two": {"expires_at": now + timedelta(hours=1)},
        "preferans_rooms/room-b/preferans_media/current": {
            "expires_at": now - timedelta(minutes=2)
        },
    }
    db = DB(state)
    original = dict(state)
    dry = module.cleanup(db, now=now, apply=False, max_rooms=2, max_deletes=2)
    assert dry == {"rooms_scanned": 2, "expired_found": 3, "deleted": 0}
    assert state == original
    apply = module.cleanup(db, now=now, apply=True, max_rooms=1, max_deletes=2)
    assert apply["deleted"] == 2
    assert "preferans_rooms/room-a/preferans_media/current" not in state
    assert "preferans_rooms/room-a/preferans_media_ops/one" not in state
    assert "preferans_rooms/room-a/preferans_media_ops/two" in state
    assert "preferans_rooms/room-b/preferans_media/current" in state


def test_legacy_docs_without_expiry_not_deleted():
    now = datetime(2026, 11, 23, tzinfo=UTC)
    state = {
        "preferans_rooms/room-a": {"status": "closed"},
        "preferans_rooms/room-a/preferans_media/current": {"signals": []},
    }
    result = module.cleanup(DB(state), now=now, apply=True, max_rooms=1, max_deletes=10)
    assert result["deleted"] == 0
    assert "preferans_rooms/room-a/preferans_media/current" in state
