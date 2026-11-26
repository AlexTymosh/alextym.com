"""Notebook awards use the authoritative ranking arithmetic and private seat projection."""

from dataclasses import replace

import pytest

from preferans.domain.history import final_result
from preferans.domain.ledger import ScoreState
from preferans.online.punch_choices import effective, initial, notebook_awards
from preferans.online.views import seat_view

ROOM = {
    "id": "a" * 32,
    "status": "closed",
    "seats": ["a", "b", "c"],
    "admin_uid": "a",
    "game_id": "deal",
}


def score_with(vists):
    score = ScoreState.new()
    return replace(score, pool=(score.target,) * 3, closed=True, vists=vists)


@pytest.mark.parametrize("status", ["awaiting_settlement", "closed"])
def test_notebook_example_and_seat_privacy(status):
    score = score_with(((0, 0, 0), (27, 0, 0), (34, 15, 0)))
    expected = [
        {"from": 1, "to": 0, "bare": 0, "ordinary": 2},
        {"from": 2, "to": 0, "bare": 0, "ordinary": 3},
        {"from": 2, "to": 1, "bare": 0, "ordinary": 1},
    ]
    room = {**ROOM, "status": status}
    for uid in ROOM["seats"]:
        view = seat_view(room, None, score, uid, 1)
        assert view["final_settlement"]["net"] == [-61, 12, 49]
        assert view["final_punches"] == expected
    assert final_result(room, score, 100)["punches"] == expected
    assert "final_punches" not in seat_view(room, None, score, "observer", 1, owner=True)
    assert "final_punches" not in seat_view({**ROOM, "sheet_loser": 0}, None, score, "a", 1)
    assert "final_punches" not in seat_view({**ROOM, "status": "playing"}, None, score, "a", 1)


def test_exempt_second_place_and_triple_tie():
    score = score_with(((0, 0, 105), (5, 0, 15), (0, 0, 0)))
    view = seat_view(ROOM, None, score, "a", 1)
    assert view["final_settlement"]["net"] == [100, 20, -120]
    assert {(p["from"], p["to"]) for p in view["final_punches"]} == {(0, 2), (1, 2)}
    tie = score_with(((0, 0, 0),) * 3)
    assert seat_view(ROOM, None, tie, "a", 1)["final_punches"] == []


def test_snapshot_and_replacement_match_history_without_mutation():
    score = score_with(((0, 0, 501), (0, 0, 0), (0, 0, 0)))
    result = final_result(ROOM, score, 100)
    choices = initial(result)
    first = next(p for p in choices if p["from"] == 0)
    first["replacement"] = 1
    room = {**ROOM, "final_punches": result["punches"], "punch_choices": choices}
    view = seat_view(room, None, score, "a", 2)
    assert view["final_punches"] == effective(result, choices)["punches"]
    assert next(p for p in view["final_punches"] if p["from"] == 0) == {
        "from": 0,
        "to": 2,
        "bare": 1,
        "ordinary": 11,
    }
    assert next(p for p in result["punches"] if p["from"] == 0)["bare"] == 2
    assert (
        seat_view({**room, "status": "awaiting_settlement"}, None, score, "a", 2)["final_punches"]
        == result["punches"]
    )
    # Legacy rooms retain the stored bare-pair choice even if the current
    # fallback no longer proposes that pair.
    assert notebook_awards([], [first]) == [{"from": 0, "to": 2, "bare": 1, "ordinary": 11}]
