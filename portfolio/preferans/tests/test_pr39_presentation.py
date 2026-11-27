from types import SimpleNamespace

import pytest

from preferans.online.pause_clock import reasons, transition
from preferans.online.presentation import (
    PresentationError,
    change,
    close_after_move,
    close_widow_after_defense,
    initial,
)

ROOM = {"status": "playing", "game_id": "deal"}


def action(control, game, seat, name, **args):
    revision = control.get("presentation", initial())["revision"]
    return change(control, ROOM, game, seat, name, {"presentation_version": revision, **args}, 1000)


def test_discard_review_not_paused_and_only_opener_can_close():
    game = SimpleNamespace(declarer=0, discarded=(1, 2))
    control = {"paused_at": None}
    action(control, game, 0, "overlay_open", kind="discard_replay")
    assert not reasons(control)
    with pytest.raises(PresentationError) as error:
        action(control, game, 1, "overlay_close", overlay_id=1)
    assert error.value.code == 403
    assert control["presentation"]["overlay"]["seat"] == 0
    action(control, game, 0, "overlay_close", overlay_id=1)
    assert control["presentation"]["overlay"] is None
    for name in ("declare", "play"):
        action(control, game, 0, "overlay_open", kind="discard_replay")
        close_after_move(control, 2000, name)
        assert control["presentation"]["overlay"] is None
    transition(control, {"break"}, 1000)
    action(control, game, 0, "overlay_open", kind="discard_replay")
    assert reasons(control) == {"break"}


def test_normal_widow_overlay_ends_after_defense():
    game = SimpleNamespace(
        widow_revealed=2, is_passout=False, phase="defense_second", trick=(), completed_tricks=()
    )
    control = {"paused_at": None}
    action(control, game, 1, "overlay_open", kind="widow_replay")
    game.phase = "choose_mode"
    close_widow_after_defense(control, game, 2000)
    assert control["presentation"]["overlay"] is None
    assert not reasons(control)
    with pytest.raises(PresentationError):
        action(control, game, 1, "overlay_open", kind="widow_replay")
