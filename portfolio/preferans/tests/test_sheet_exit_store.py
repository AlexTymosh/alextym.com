"""Repository integration of the technical finish using existing Firestore fixture."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from preferans.online import store
from preferans.online.codec import decode
from test_secure_rooms import FakeDB, FakeTransaction, transactional
from test_realtime_store import setup_realtime  # noqa: F401


def setup(monkeypatch):
    monkeypatch.setenv("PREFERANS_REALTIME_ENABLED", "false")
    db = FakeDB()
    api = store.FirestoreRooms(
        db,
        firestore_module=SimpleNamespace(transactional=transactional),
        now_ms=lambda: 1_800_000_000_000,
    )
    rid = api.create("a", "exit-create-001")["room_id"]
    api.join(rid, "b", "exit-join-b001", 0)
    api.join(rid, "c", "exit-join-c001", 1)
    api.start(rid, "a", "exit-start-001", 2, False)
    return api, rid


def do(api, rid, uid, key, action, args):
    return api.command(rid, uid, key, api.view(rid, uid)["version"], action, args)


def check_final(api, rid, loser, before_score):
    result = api.result(rid, "a")
    assert result["reason"] == "sheet_discarded"
    assert [p["gold"] for p in result["players"]] == [int(i != loser) for i in range(3)]
    assert [p["technical_losses"] for p in result["players"]] == [int(i == loser) for i in range(3)]
    assert [p["net_vists"] for p in result["players"]] == [0, 0, 0]
    assert result["punches"] == [
        {"from": i, "to": loser, "bare": 1, "ordinary": 0} for i in range(3) if i != loser
    ]
    state = api.db.docs[f"preferans_rooms/{rid}/private/current"]
    assert decode(state["score"]) == before_score
    assert state["controls"]["timer"] is None and state["controls"]["vote"] is None
    for uid in "abc":
        view = api.view(rid, uid)
        assert view["status"] == "closed" and view["sheet_loser"] == loser
        assert all(
            k not in view
            for k in (
                "hand",
                "open_hands",
                "legal_cards",
                "widow",
                "sheet_offers",
                "next_deal",
                "presentation",
            )
        )
    return result


def test_voluntary_finish_atomic_rankings_and_idempotency(monkeypatch):
    api, rid = setup(monkeypatch)
    before = decode(api.db.docs[f"preferans_rooms/{rid}/private/current"]["score"])
    version = api.view(rid, "b")["version"]
    args = {"confirm": True}
    result = api.command(rid, "b", "exit-voluntary1", version, "sheet_discard", args)
    final = check_final(api, rid, 1, before)
    saved = copy.deepcopy(api.db.docs)
    assert api.command(rid, "b", "exit-voluntary1", version, "sheet_discard", args) == result
    assert api.db.docs == saved
    for uid in "abc":
        with pytest.raises(store.StoreError):
            do(api, rid, uid, f"second-exit-{uid}", "sheet_discard", args)
    assert api.result(rid, "a") == final
    ranks = api.rankings("a")["rankings"]
    assert sum(r["gold"] for r in ranks) == 2 and sum(r["technical_losses"] for r in ranks) == 1
    assert all(r["games"] == 1 for r in ranks)
    with pytest.raises(store.StoreError):
        api.admin_adjust(
            rid,
            "a",
            "exit-late-adjust",
            result["version"],
            {"field": "hill", "seat": 0, "against": None, "delta": 1, "reason": "late adjustment"},
            False,
        )
    assert api.db.docs == saved


def test_retired_offer_commands_do_not_change_storage(monkeypatch):
    api, rid = setup(monkeypatch)
    saved = copy.deepcopy(api.db.docs)
    for action, args in (
        ("sheet_offer", {"target": 1}),
        ("sheet_reply", {"offer_id": 5, "accept": True}),
    ):
        with pytest.raises(store.StoreError) as exc:
            do(api, rid, "b", "retired-offer-001", action, args)
        assert exc.value.code == 422
    assert api.db.docs == saved


def test_failed_final_commit_does_not_create_result(monkeypatch):
    api, rid = setup(monkeypatch)
    saved = copy.deepcopy(api.db.docs)
    version = api.view(rid, "b")["version"]

    def fail(_self):
        raise RuntimeError("failed commit")

    monkeypatch.setattr(FakeTransaction, "commit", fail)
    with pytest.raises(RuntimeError, match="failed commit"):
        api.command(rid, "b", "exit-failed-001", version, "sheet_discard", {"confirm": True})
    assert api.db.docs == saved


def test_exit_during_shared_pause_is_terminal_and_published(setup_realtime):  # noqa: F811
    api, rid, clock, runtime, tickets, conns = setup_realtime
    current = api.view(rid, "a")
    api.command(
        rid,
        "a",
        "exit-overlay-01",
        current["version"],
        "overlay_open",
        {"kind": "score_sheet", "presentation_version": current["presentation"]["revision"]},
    )
    assert api.view(rid, "b")["controls"]["paused"]
    before = decode(api.db.docs[f"preferans_rooms/{rid}/private/current"]["score"])
    do(api, rid, "b", "exit-paused-001", "sheet_discard", {"confirm": True})
    check_final(api, rid, 1, before)
    for t, c in zip(tickets, conns):
        assert runtime.snapshot(t, c, clock[0])["sheet_loser"] == 1
    version = api.view(rid, "a")["version"]
    api.sync_realtime(rid, "a")
    assert api.view(rid, "a")["version"] == version
