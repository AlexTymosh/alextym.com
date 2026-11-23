"""PR7: immutable history, all tie ranks, ranking projection and no double medals."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from preferans.domain.history import (
    final_result,
    placement_outcome,
    public_player_id,
    update_ranking,
)
from preferans.domain.ledger import ScoreState
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def test_rank_winner_and_equal_bottom():
    one = placement_outcome((100, 50, -150))
    assert one["places"] == [1, 2, 3]
    assert one["golds"] == [1, 0, 0]
    lower_tie = placement_outcome((10, -5, -5))
    assert lower_tie["places"] == [1, 2, 2]
    assert lower_tie["silvers"] == [0, 1, 1]


def test_two_tied_first_and_triple_tie():
    two = placement_outcome((40, 40, -80))
    assert two["places"] == [1, 1, 3]
    assert two["golds"] == [1, 1, 0]
    all_tied = placement_outcome((0, 0, 0))
    assert all_tied["places"] == [None, None, None]
    assert all_tied["golds"] == [0, 0, 0]


def test_sheet_discard_has_two_winners_and_directed_bare_punches():
    result = placement_outcome((0, 0, 0), sheet_loser=1)
    assert result["places"] == [1, 3, 1]
    assert result["golds"] == [1, 0, 1]
    assert result["technical_losses"] == [0, 1, 0]
    assert result["punches"] == [
        {"from": 0, "to": 1, "bare": 1, "ordinary": 0},
        {"from": 2, "to": 1, "bare": 1, "ordinary": 0},
    ]


def complete_score(hill=(0, 6, 0)):
    initial = ScoreState.new()
    return replace(
        initial, pool=(20, 20, 20), hill=hill, closed=True, deal_ids=("deal-001",), version=1
    )


def test_final_result_does_not_expose_uids_and_net_zero():
    room = {"id": "a" * 32, "seats": ["auth-A", "auth-B", "auth-C"], "started_at_ms": 1_000}
    final = final_result(room, complete_score(), 10_000)
    assert final["duration_ms"] == 9_000
    assert sum(player["net_vists"] for player in final["players"]) == 0
    assert [player["place"] for player in final["players"]] == [1, 3, 1]
    assert "auth-A" not in json.dumps(final)
    assert "auth-B" not in json.dumps(final)
    assert "auth-C" not in json.dumps(final)
    assert final["punches_confirmed"] is False


def test_no_invented_duration_for_pre_pr07_game():
    room = {"id": "a" * 32, "seats": ["a", "b", "c"]}
    result = final_result(room, complete_score(), 10_000)
    assert result["duration_ms"] is None and result["started_at_ms"] is None
    aggregate = update_ranking(None, result["players"][0], result)
    assert aggregate["games"] == 1
    assert aggregate["timed_games"] == 0
    assert aggregate["total_duration_ms"] == 0


def test_final_result_requires_a_closed_game():
    with pytest.raises(ValueError):
        final_result({"id": "a" * 32, "seats": ["a", "b", "c"]}, ScoreState.new(), 1)


def test_public_player_id_stable_and_not_literal_uid():
    assert public_player_id("player-a") == public_player_id("player-a")
    assert public_player_id("player-a") != public_player_id("player-b")
    assert "player-a" not in public_player_id("player-a")


def session(db, clock, index=1):
    api = FirestoreRooms(
        db, firestore_module=SimpleNamespace(transactional=transactional), now_ms=lambda: clock[0]
    )
    room = api.create("auth-A", f"create-room-{index:04d}")["room_id"]
    api.join(room, "auth-B", f"join-bbb-{index:04d}", 0)
    api.join(room, "auth-C", f"join-ccc-{index:04d}", 1)
    api.start(room, "auth-A", f"start-room-{index:04d}", 2, False)
    doc = f"preferans_rooms/{room}"
    db.docs[doc]["status"] = "awaiting_settlement"
    return api, room


def test_atomic_close_creates_immutable_result_and_ranking_once(monkeypatch):
    from preferans.online import store as store_module

    monkeypatch.setattr(store_module, "settle_game", lambda *_args, **_kwargs: complete_score())
    db = FakeDB()
    clock = [1_800_000_000_000]
    api, rid = session(db, clock)
    room_ref = f"preferans_rooms/{rid}"
    before = db.docs[room_ref]["version"]
    clock[0] += 5_000
    payload = {"regular_route": "pool", "passout_routes": ["pool"] * 3}
    saved = api.settle(rid, "auth-A", "settle-unique-01", before, payload, False)
    assert db.docs[room_ref]["status"] == "closed"
    result_key = f"preferans_results/{rid}"
    result = db.docs[result_key]
    assert result["room_id"] == rid
    assert result["deal_count"] == 1
    assert result["duration_ms"] == 5_000
    assert [p["gold"] for p in result["players"]] == [1, 0, 1]
    # Exact retry returns the idempotent response; neither medal nor result repeats.
    assert api.settle(rid, "auth-A", "settle-unique-01", before, payload, False) == saved
    ranks = api.rankings("another-granted-user")["rankings"]
    assert len(ranks) == 3
    assert sum(row["gold"] for row in ranks) == 2
    assert all(row["games"] == 1 for row in ranks)
    assert api.result(rid, "another-granted-user") == result
    assert api.history("another-granted-user")["results"] == [result]
    assert api.history("another-granted-user")["has_more"] is False
    with pytest.raises(StoreError) as exc:
        api.settle(rid, "auth-A", "settle-different-01", saved["version"], payload, False)
    assert exc.value.code == 409
    assert db.docs[result_key] == result
    with pytest.raises(StoreError) as exc:
        api.admin_adjust(
            rid,
            "auth-A",
            "adjust-too-late",
            saved["version"],
            {"field": "hill", "seat": 1, "against": None, "delta": 5, "reason": "late adjustment"},
            False,
        )
    assert exc.value.code == 409


def test_rankings_all_games_and_history_page(monkeypatch):
    from preferans.online import store as store_module

    monkeypatch.setattr(store_module, "settle_game", lambda *_args, **_kwargs: complete_score())
    db = FakeDB()
    clock = [1_800_000_000_000]
    api, a = session(db, clock, 1)
    api.settle(
        a,
        "auth-A",
        "settle-unique-01",
        db.docs[f"preferans_rooms/{a}"]["version"],
        {"regular_route": "pool", "passout_routes": ["pool"] * 3},
        False,
    )
    clock[0] += 90_000
    api, b = session(db, clock, 2)
    api.settle(
        b,
        "auth-A",
        "settle-unique-02",
        db.docs[f"preferans_rooms/{b}"]["version"],
        {"regular_route": "pool", "passout_routes": ["pool"] * 3},
        False,
    )
    assert len(api.history("auth-A", limit=1)["results"]) == 1
    assert api.history("auth-A", limit=1)["has_more"] is True
    assert api.history("auth-A", limit=1)["results"][0]["room_id"] == b
    assert all(row["games"] == 2 for row in api.rankings("auth-A")["rankings"])
    assert sum(row["gold"] for row in api.rankings("auth-A")["rankings"]) == 4


def test_history_rejects_invalid_limits_and_ids():
    api = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    for limit in (0, 101, "50", True):
        with pytest.raises(StoreError) as exc:
            api.history("auth-A", limit)
        assert exc.value.code == 422
    with pytest.raises(StoreError) as exc:
        api.result("../../credentials", "auth-A")
    assert exc.value.code == 404
