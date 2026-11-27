"""PR13 shared state: pure clock and permission regressions."""

from types import SimpleNamespace

import pytest

from preferans.online.pause_clock import reasons, transition
from preferans.online.presentation import (
    PresentationError,
    allows_replay_move,
    change,
    close_after_move,
    initial,
    invalidate_ready,
    music_position,
    projection,
)

ROOM = {"status": "playing", "game_id": "deal-a"}
GAME = SimpleNamespace(completed_tricks=[object()], widow_revealed=1)


def control():
    return {
        "paused_at": None,
        "presence": [100_000] * 3,
        "timer": {"deadline_ms": 180_000},
        "next_deal": {"deadline_ms": 105_000},
        "vote": None,
    }


def act(c, seat, action, at=100_000, **args):
    return change(
        c,
        ROOM,
        GAME,
        seat,
        action,
        {"presentation_version": c.get("presentation", initial())["revision"], **args},
        at,
    )


def test_overlay_replace_and_any_seat_close():
    c = control()
    act(c, 0, "overlay_open", kind="score_sheet")
    assert c["timer"]["deadline_ms"] == 180_000
    act(c, 1, "overlay_open", 103_000, kind="radio")
    assert c["timer"]["remaining_ms"] == 77_000
    assert projection(c, True, 103_000)["overlay"]["seat"] == 1
    act(c, 2, "overlay_close", 104_000, overlay_id=2)
    assert c["timer"]["deadline_ms"] == 181_000
    assert c["next_deal"]["deadline_ms"] == 109_000


def test_break_independent_and_unanimous():
    c = control()
    act(c, 0, "overlay_open", kind="score_sheet")
    act(c, 1, "break_start")
    act(c, 2, "overlay_close", overlay_id=1)
    assert reasons(c) == {"break"}
    for seat in (0, 1):
        act(c, seat, "break_ready", break_id=2, ready=True)
    assert c["paused_at"] is not None
    transition(c, {"break", "connection_lost"}, 100_000)
    act(c, 2, "break_ready", break_id=2, ready=True)
    assert reasons(c) == {"connection_lost"}
    assert c["timer"]["deadline_ms"] is None


def test_disconnect_clears_ready_and_recovery_clears_all():
    c = control()
    act(c, 0, "break_start")
    act(c, 0, "break_ready", break_id=1, ready=True)
    act(c, 1, "break_ready", break_id=1, ready=True)
    assert invalidate_ready(c, [100_000, None, 100_000], False)
    assert c["presentation"]["break"]["ready"] == [True, False, False]
    assert invalidate_ready(c, [100_000] * 3, True)
    assert c["presentation"]["break"]["ready"] == [False] * 3


def test_last_trick_exception_only_without_other_reasons():
    c = control()
    act(c, 0, "overlay_open", kind="last_trick")
    assert allows_replay_move(c)
    transition(c, {"shared_overlay", "break"}, 100_000)
    assert not allows_replay_move(c)
    close_after_move(c, 100_000)
    assert c["presentation"]["overlay"]
    transition(c, {"shared_overlay"}, 100_000)
    close_after_move(c, 101_000)
    assert not c["presentation"]["overlay"]
    assert c["paused_at"] is None


def test_stale_revision_wrong_overlay_and_hidden_widow():
    c = control()
    act(c, 0, "overlay_open", kind="last_trick")
    with pytest.raises(PresentationError) as exc:
        change(
            c, ROOM, GAME, 1, "overlay_open", {"presentation_version": 0, "kind": "radio"}, 100_000
        )
    assert exc.value.code == 409
    with pytest.raises(PresentationError):
        act(c, 1, "overlay_close", overlay_id=99)
    with pytest.raises(PresentationError):
        change(
            c,
            ROOM,
            SimpleNamespace(widow_revealed=0),
            1,
            "overlay_open",
            {"presentation_version": 1, "kind": "widow_replay"},
            100_000,
        )
    assert c["presentation"]["overlay"]["kind"] == "last_trick"


def test_music_continues_with_overlay_closed_and_no_clock_writes():
    c = control()
    act(c, 0, "overlay_open", kind="radio")
    act(c, 2, "music", command="play")
    act(c, 1, "overlay_close", overlay_id=1)
    m = c["presentation"]["music"]
    assert music_position(m, 113_000) == (1, 1000)
    assert music_position(m, 125_000) == (0, 1000)
    act(c, 1, "overlay_open", 125_000, kind="radio")
    act(c, 2, "music", 125_000, command="pause")
    assert music_position(c["presentation"]["music"], 200_000) == (0, 1000)


def test_external_pause_freezes_vote_without_self_deadlock():
    c = control()
    c["vote"] = {"deadline_ms": 120_000}
    c["timer"] = {"deadline_ms": None, "remaining_ms": 80_000}
    act(c, 0, "break_start")
    assert c["vote"]["remaining_ms"] == 20_000
    for seat in range(3):
        act(c, seat, "break_ready", 105_000, break_id=1, ready=True)
    assert c["vote"]["deadline_ms"] == 125_000
    assert c["timer"]["deadline_ms"] is None


def test_projection_is_allowlisted_and_legacy_gate():
    c = control()
    assert projection(c, False, 100_000) is None
    act(c, 0, "overlay_open", kind="score_sheet")
    c["presentation"]["overlay"]["private"] = "secret"
    assert "private" not in projection(c, True, 100_000)["overlay"]
    assert not projection(c, False, 100_000)["enabled"]


def test_normal_widow_review_cannot_reopen_after_defense():
    game = SimpleNamespace(
        widow_revealed=2, is_passout=False, phase="defense_second", trick=[], completed_tricks=[]
    )
    c = control()
    change(
        c,
        ROOM,
        game,
        1,
        "overlay_open",
        {"presentation_version": 0, "kind": "widow_replay"},
        100_000,
    )
    game.phase = "play"
    for trick, completed in [([], []), ([object()], []), ([], [object()])]:
        game.trick = trick
        game.completed_tricks = completed
        with pytest.raises(PresentationError) as exc:
            change(
                control(),
                ROOM,
                game,
                1,
                "overlay_open",
                {"presentation_version": 0, "kind": "widow_replay"},
                100_000,
            )
        assert exc.value.code == 409
