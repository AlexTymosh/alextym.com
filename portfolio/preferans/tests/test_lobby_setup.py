"""PR11 lobby security, directory projection and readiness regression."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from preferans.online import router as api
from preferans.online.lobby import can_create_room, directory, profile_projection, room_profiles
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def test_project_admin_only_create(monkeypatch):
    called = []
    monkeypatch.setattr(api, "_execute", lambda *args, **kwargs: called.append(kwargs) or {})
    for role in (None, "View", "Test"):
        req = SimpleNamespace(state=SimpleNamespace(portfolio_lab_role=role, preferans_owner=False))
        with pytest.raises(HTTPException) as exc:
            api.create_room(req, api.Create(idempotency_key="create-test-01"))
        assert exc.value.status_code == 403
    assert called == []
    req = SimpleNamespace(state=SimpleNamespace(portfolio_lab_role="Admin", preferans_owner=False))
    assert api.create_room(req, api.Create(idempotency_key="create-test-01")) == {}
    assert called == [{"token": "create-test-01", "require_ready": True}]
    assert can_create_room(None, True)
    assert not can_create_room("Test", False)


def test_new_lobby_requires_all_three_and_resets_after_configuration(monkeypatch):
    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    svc = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    rid = svc.create("a", "create-lobby-01", require_ready=True)["room_id"]
    svc.join(rid, "b", "join-lobby-b", 0)
    svc.join(rid, "c", "join-lobby-c", 1)
    assert svc.view(rid, "a")["lobby_setup"]["ready"] == [False, False, False]
    with pytest.raises(StoreError) as early:
        svc.start(rid, "a", "early-start-01", 2, False)
    assert early.value.code == 409
    with pytest.raises(StoreError) as denied:
        svc.command(rid, "b", "bad-config-01", 2, "lobby_config", {"dealer": 1, "target": 30})
    assert denied.value.code == 403
    for i, uid in enumerate("abc"):
        svc.command(rid, uid, f"ready-lobby-{i}", 2 + i, "lobby_ready", {"ready": True})
    svc.command(rid, "a", "config-lobby-01", 5, "lobby_config", {"dealer": 1, "target": 30})
    setup = svc.view(rid, "c")["lobby_setup"]
    assert setup["ready"] == [False, False, False]
    assert setup["dealer"] == 1 and setup["target"] == 30
    for i, uid in enumerate("abc"):
        svc.command(rid, uid, f"ready-again-{i}", 6 + i, "lobby_ready", {"ready": True})
    svc.start(rid, "a", "start-lobby-01", 9, False)
    view = svc.view(rid, "b")
    assert view["dealer"] == 1 and view["first_hand"] == 2
    assert view["score"]["target"] == 30
    assert "lobby_setup" not in view
    assert len(view["hand"]) == 10


class Query:
    def __init__(self, rows):
        self.rows = rows

    def where(self, *, filter):
        def matches(row):
            value = row.get(filter.field_path)
            return (
                filter.value in value
                if filter.op_string == "array_contains"
                else value == filter.value
            )

        return Query([row for row in self.rows if matches(row)])

    def limit(self, count):
        return Query(self.rows[:count])

    def stream(self, timeout):
        return iter(SimpleNamespace(to_dict=lambda row=row: row) for row in self.rows)


def test_directory_exposes_only_own_or_joinable_rooms():
    rows = [
        {"id": "a" * 32, "status": "playing", "seats": ["me", "b", "c"], "created_at_ms": 1},
        {"id": "b" * 32, "status": "playing", "seats": ["x", "b", "c"], "created_at_ms": 2},
        {"id": "c" * 32, "status": "lobby", "seats": ["x", None, None], "created_at_ms": 3},
        {"id": "d" * 32, "status": "lobby", "seats": ["x", "b", "c"], "created_at_ms": 4},
        {"id": "e" * 32, "status": "closed", "seats": ["me", "b", "c"], "created_at_ms": 5},
    ]
    db = SimpleNamespace(collection=lambda _: Query(rows))
    result = directory(db, "me", admin=False)
    assert [room["room_id"] for room in result["rooms"]] == ["a" * 32, "c" * 32]
    assert result["rooms"][0] == {
        "room_id": "a" * 32,
        "status": "playing",
        "occupied": [True, True, True],
        "mine": True,
        "created_at_ms": 1,
        "daily_number": None,
        "waiting_names": [],
        "player_names": [None, None, None],
    }
    assert not result["can_create"] and not result["truncated"]
    assert "seats" not in str(result) and "email" not in str(result)


def test_profile_allowlist_and_membership():
    db = FakeDB()
    rid = "f" * 32
    db.docs[f"preferans_rooms/{rid}"] = {"id": rid, "status": "lobby", "seats": ["a", "b", None]}
    db.docs["portfolio_lab_profiles/a"] = {
        "first_name": "Synthetic",
        "last_name": "Player",
        "email": "secret@example.invalid",
        "avatar_source": "upload",
        "avatar_data_url": "data:image/webp;base64,YWJj",
    }
    db.docs["portfolio_lab_profiles/b"] = {
        "first_name": "private@example.invalid",
        "avatar_source": "account",
        "avatar_data_url": "https://example.invalid/avatar",
    }
    result = room_profiles(db, rid, "a")
    assert result == {
        "profiles": [
            {"name": "Synthetic Player", "avatar": "data:image/webp;base64,YWJj"},
            {"name": None, "avatar": None},
            {"name": None, "avatar": None},
        ]
    }
    with pytest.raises(StoreError) as exc:
        room_profiles(db, rid, "stranger")
    assert exc.value.code == 404
    assert (
        profile_projection(
            {"avatar_source": "upload", "avatar_data_url": "data:image/svg+xml;base64,YWJj"}
        )["avatar"]
        is None
    )


def test_directory_profile_budget_and_safe_names(monkeypatch):
    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    rows = [
        {"id": f"{i:032x}", "status": "lobby", "seats": ["me", f"guest-{i}", None]}
        for i in range(40)
    ]
    reads = []

    def document(uid):
        def get(timeout):
            reads.append(uid)
            record = {"first_name": "Player", "last_name": uid, "email": "private@example.invalid"}
            return SimpleNamespace(exists=True, to_dict=lambda: record)

        return SimpleNamespace(get=get)

    def collection(name):
        if name == "preferans_rooms":
            return Query(rows)
        assert name == "portfolio_lab_profiles"
        return SimpleNamespace(document=document)

    result = directory(SimpleNamespace(collection=collection), "me", admin=False)
    assert len(reads) == 30 and len(set(reads)) == 30
    assert all(room["player_names"][0] == "Player me" for room in result["rooms"])
    assert all(room["player_names"][2] is None for room in result["rooms"])
    assert "private@example.invalid" not in str(result)
    assert any(room["player_names"][1] is None for room in result["rooms"])


def test_preferans_alias_is_optional_and_does_not_replace_account_name():
    record = {"first_name": "Player", "last_name": "One", "preferans_alias": "Nickname"}
    result = profile_projection(record)
    assert result == {"name": "Player One", "avatar": None, "alias": "Nickname"}
    for invalid in ("", "name@example.invalid", "a" * 41, 12, "a\u202eb"):
        assert "alias" not in profile_projection({**record, "preferans_alias": invalid})
