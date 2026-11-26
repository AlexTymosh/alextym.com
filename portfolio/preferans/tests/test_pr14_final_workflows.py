"""Final-workflow regressions using the existing transaction fake."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from preferans.online import ruleset_catalog, store
from test_history_ranking import complete_score, session
from test_secure_rooms import FakeDB, transactional
from test_sheet_exit_store import do, setup


def ready_presence(api, rid):
    for uid in "abc":
        do(api, rid, uid, f"presence-pr14-{uid}", "pulse", {})


def test_retired_reveal_commands_are_rejected_without_storage_changes(monkeypatch):
    api, rid = setup(monkeypatch)
    ready_presence(api, rid)
    before = deepcopy(api.db.docs)
    for action, args in (
        ("reveal_report", {"card": api.view(rid, "a")["hand"][0]}),
        ("reveal_propose", {}),
        ("reveal_vote", {}),
    ):
        with pytest.raises(store.StoreError):
            do(api, rid, "a", "retired-" + action, action, args)
    assert api.db.docs == before


def test_punch_choice_keeps_result_and_updates_both_rankings_once(monkeypatch):
    monkeypatch.setenv("PREFERANS_REALTIME_ENABLED", "false")
    monkeypatch.setattr(store, "settle_game", lambda *_a, **_kw: complete_score(hill=(0, 300, 0)))
    db = FakeDB()
    api, rid = session(db, [1_800_000_000_000])
    api.settle(
        rid,
        "auth-A",
        "settle-pr14-01",
        db.docs[f"preferans_rooms/{rid}"]["version"],
        {"regular_route": "pool", "passout_routes": ["pool"] * 3},
        False,
    )
    ref = f"preferans_results/{rid}"
    assert ref not in db.docs
    assert api.view(rid, "auth-A")["final_review"] is True

    api.command(
        rid,
        "auth-A",
        "confirm-pr14-01",
        api.view(rid, "auth-A")["version"],
        "final_confirm",
        {},
    )
    assert api.view(rid, "auth-A")["status"] == "closed"
    original = deepcopy(db.docs[ref])
    pair = api.view(rid, "auth-B")["punch_choices"][0]
    assert pair["to"] == 1 and pair["bare"] >= 1
    args = {"from": pair["from"], "replace": 1}
    version = api.view(rid, "auth-B")["version"]
    with pytest.raises(store.StoreError):
        api.command(rid, "auth-A", "wrong-choice-01", version, "punch_choose", args)
    before = {row["id"]: row for row in api.rankings("auth-A")["rankings"]}
    response = api.command(rid, "auth-B", "choice-pr14-01", version, "punch_choose", args)
    assert api.command(rid, "auth-B", "choice-pr14-01", version, "punch_choose", args) == response
    assert db.docs[ref] == original
    effective = api.result(rid, "auth-A")
    assert effective["ledger_sha256"] == original["ledger_sha256"]
    after = {row["id"]: row for row in api.rankings("auth-A")["rankings"]}
    for seat, side in ((pair["from"], "given"), (pair["to"], "received")):
        uid = original["players"][seat]["id"]
        assert after[uid][f"bare_{side}"] == before[uid][f"bare_{side}"] - 1
        assert after[uid][f"ordinary_{side}"] == before[uid][f"ordinary_{side}"] + 10
        assert after[uid]["games"] == before[uid]["games"]
    with pytest.raises(store.StoreError):
        do(api, rid, "auth-B", "duplicate-choice-02", "punch_choose", args)


def test_versioned_ruleset_selection_and_archive(monkeypatch):
    monkeypatch.setenv("PREFERANS_REALTIME_ENABLED", "false")
    db = FakeDB()
    fs = SimpleNamespace(transactional=transactional)
    api = store.FirestoreRooms(db, firestore_module=fs, now_ms=lambda: 1000)
    initial = ruleset_catalog.base()
    body = {
        "id": "a" * 32,
        "expected_version": 0,
        "name": "Test template",
        "description": "",
        "parameters": {**initial["parameters"], "pool_target": 26},
        "policy": initial["policy"],
    }
    v1 = ruleset_catalog.save(db, fs, "owner", body, 1000)
    assert ruleset_catalog.save(db, fs, "owner", body, 1001) == v1
    v2 = ruleset_catalog.save(
        db,
        fs,
        "owner",
        {**body, "expected_version": 1, "parameters": {**body["parameters"], "pool_target": 30}},
        1002,
    )
    assert v2["version"] == 2 and v2["snapshot_hash"] != v1["snapshot_hash"]
    rid = api.create("a", "create-final-01", require_ready=True)["room_id"]
    api.join(rid, "b", "join-final-b", 0)
    api.join(rid, "c", "join-final-c", 1)
    do(api, rid, "a", "select-final-01", "ruleset_select", {"id": v1["id"], "version": 1})
    assert api.view(rid, "a")["lobby_setup"]["target"] == 26
    for uid in "abc":
        do(api, rid, uid, f"ready-final-{uid}", "lobby_ready", {"ready": True})
    version = api.view(rid, "a")["version"]
    api.start(rid, "a", "start-final-01", version, False)
    view = api.view(rid, "a")
    assert view["score"]["target"] == 26
    with pytest.raises(store.StoreError) as exc:
        do(api, rid, "a", "archive-denied-01", "archive", {"reason": "Test archive"})
    assert exc.value.code == 403
    api.command(
        rid,
        "owner",
        "archive-final-01",
        view["version"],
        "archive",
        {"reason": "Test archive"},
        owner=True,
    )
    archived = api.view(rid, "a")
    assert archived["status"] == "archived" and "hand" not in archived
    assert archived["score"] == view["score"]
    assert f"preferans_results/{rid}" not in db.docs
    assert not api.rankings("a")["rankings"]
    with pytest.raises(store.StoreError):
        do(api, rid, "a", "archived-pass-01", "pass", {})
