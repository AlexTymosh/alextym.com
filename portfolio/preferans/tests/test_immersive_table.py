"""PR15 server-side privacy, numbering, accounting and dealer contracts."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from preferans.online.table_presentation import notebook, room_day


def test_running_notebook_merges_corrections_in_ledger_order():
    from preferans.domain.ledger import EntryKind, LedgerEntry

    def entry(seq, kind, actor, amount, against=None):
        return LedgerEntry(
            sequence=seq,
            deal_id="deal-1" if seq <= 2 else "deal-2",
            kind=EntryKind(kind),
            actor=actor,
            amount=amount,
            reason="test_posting",
            against=against,
        )

    score = SimpleNamespace(
        hill=(6, 0, 0),
        pool=(2, 0, 0),
        vists=((0, 4, 0), (0, 0, 0), (0, 0, 0)),
        entries=(
            entry(1, "hill", 0, 4),
            entry(2, "hill", 0, 6),
            entry(3, "pool", 0, 2),
            entry(4, "vist", 0, 4, 1),
        ),
    )
    correction = {
        "field": "hill",
        "seat": 0,
        "against": None,
        "delta": -4,
        "game_version": 15,
        "ledger_sequence": 2,
    }
    result = notebook(score, {"score_sheet_adjustments": [correction], "adjustments": [correction]})
    assert result["exact"] is True
    assert result["hill"][0] == [4, 10, 6]
    assert result["pool"][0] == [2]
    assert result["vists"][0][1] == [4]
    assert result["vists"][1][0] == []
    assert {"field": "hill", "seat": 0, "against": None, "index": 2, "manual": True} in result[
        "marks"
    ]
    assert {"field": "vist", "seat": 0, "against": 1, "index": 0, "latest": True} in result["marks"]
    legacy = notebook(score, {"adjustments": [correction]})
    assert legacy["exact"] is False
    assert legacy["hill"][0] == [6]


def test_london_calendar_day_includes_dst():
    at = datetime(2026, 7, 1, 23, 30, tzinfo=timezone.utc)
    assert room_day(int(at.timestamp() * 1000)) == "2026-07-02"
    at = datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)
    assert room_day(int(at.timestamp() * 1000)) == "2026-11-25"


def test_dealer_pass_requires_current_dealer_and_new_readiness(monkeypatch):
    from preferans.online.store import FirestoreRooms, StoreError
    from test_secure_rooms import FakeDB, transactional

    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    svc = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    rid = svc.create("a", "pr15-create-a", require_ready=True)["room_id"]
    svc.join(rid, "b", "pr15-join-b", 0)
    svc.join(rid, "c", "pr15-join-c", 1)
    for i, uid in enumerate("abc"):
        svc.command(rid, uid, f"pr15-ready-{i}", 2 + i, "lobby_ready", {"ready": True})
    with pytest.raises(StoreError) as denied:
        svc.command(rid, "b", "pr15-denied-pass", 5, "dealer_pass", {"dealer": 0})
    assert denied.value.code == 403
    svc.command(rid, "c", "pr15-pass-dealer", 5, "dealer_pass", {"dealer": 1})
    assert svc.view(rid, "b")["lobby_setup"]["ready"] == [False, False, False]
    assert svc.view(rid, "b")["lobby_setup"]["dealer"] == 1
    with pytest.raises(StoreError) as early:
        svc.start(rid, "b", "pr15-early-start", 6, False)
    assert early.value.code == 409
    for i, uid in enumerate("abc"):
        svc.command(rid, uid, f"pr15-ready-new-{i}", 6 + i, "lobby_ready", {"ready": True})
    result = svc.start(rid, "b", "pr15-start-game", 9, False)
    assert svc.start(rid, "b", "pr15-start-game", 9, False) == result
    assert svc.view(rid, "a")["dealer"] == 1


def test_daily_number_is_transactional_and_create_retry_does_not_increment(monkeypatch):
    from preferans.online.store import FirestoreRooms
    from test_secure_rooms import FakeDB, transactional

    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    now = [int(datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc).timestamp() * 1000)]
    db = FakeDB()
    svc = FirestoreRooms(
        db, firestore_module=SimpleNamespace(transactional=transactional), now_ms=lambda: now[0]
    )
    first = svc.create("a", "pr15-first-room")
    assert svc.create("a", "pr15-first-room") == first
    second = svc.create("b", "pr15-second-room")
    assert db.docs[f"preferans_rooms/{first['room_id']}"]["daily_number"] == 1
    assert db.docs[f"preferans_rooms/{second['room_id']}"]["daily_number"] == 2
    now[0] += 3_600_000
    third = svc.create("a", "pr15-third-room")
    assert db.docs[f"preferans_rooms/{third['room_id']}"]["daily_number"] == 1


def test_only_declarer_receives_final_discard_and_can_open_replay():
    from dataclasses import replace

    from preferans.domain.cards import FULL_DECK, deal
    from preferans.domain.game import Phase, start_game
    from preferans.domain.ledger import ScoreState
    from preferans.online.presentation import PresentationError, change, initial
    from preferans.online.views import seat_view

    game = start_game(deal(FULL_DECK, 2))
    game = replace(game, phase=Phase.DECLARE, declarer=0, discarded=game.widow)
    room = {
        "id": "a" * 32,
        "status": "playing",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "deal",
    }
    own = seat_view(room, game, ScoreState.new(), "a", 1)
    assert own["discard_count"] == 2 and len(own["own_discard"]) == 2
    for uid in ("b", "c", "owner"):
        other = seat_view(room, game, ScoreState.new(), uid, 1, owner=uid == "owner")
        assert "own_discard" not in other
    control = {"presentation": initial()}
    with pytest.raises(PresentationError) as denied:
        change(
            control,
            room,
            game,
            1,
            "overlay_open",
            {"kind": "discard_replay", "presentation_version": 0},
            100,
        )
    assert denied.value.code == 403
