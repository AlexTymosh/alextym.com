"""Durable, public shared-room state; never accepts client timestamps or cards."""

from __future__ import annotations

from .pause_clock import reasons, transition

ACTIONS = frozenset({"overlay_open", "overlay_close", "break_start", "break_ready", "music"})
OVERLAYS = frozenset({"score_sheet", "radio", "last_trick", "widow_replay", "discard_replay"})
TRACK_MS = 12_000
TRACK_COUNT = 2


class PresentationError(ValueError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def initial() -> dict:
    return {
        "revision": 0,
        "overlay": None,
        "break": None,
        "music": {"track": 0, "playing": False, "offset_ms": 0, "changed_at_ms": 0},
    }


def state(control: dict) -> dict:
    return control.setdefault("presentation", initial())


def projection(control: dict, enabled: bool, now: int) -> dict | None:
    if not enabled and "presentation" not in control:
        return None
    p = control.get("presentation") or initial()
    overlay, pause = p["overlay"], p["break"]
    return {
        "revision": p["revision"],
        "enabled": enabled,
        "server_now_ms": now,
        "overlay": {k: overlay[k] for k in ("kind", "id", "seat", "game_id", "opened_at_ms")}
        if overlay
        else None,
        "break": {"id": pause["id"], "ready": list(pause["ready"])} if pause else None,
        "music": {k: p["music"][k] for k in ("track", "playing", "offset_ms", "changed_at_ms")},
    }


def music_position(music: dict, at: int) -> tuple[int, int]:
    elapsed = max(0, at - music["changed_at_ms"]) if music["playing"] else 0
    offset = music["offset_ms"] + elapsed
    return (music["track"] + offset // TRACK_MS) % TRACK_COUNT, offset % TRACK_MS


def _keys(args: dict, extra: set[str]) -> None:
    if set(args) != {"presentation_version"} | extra:
        raise PresentationError(422, "Invalid presentation arguments")


def change(control: dict, room: dict, game, seat: int, action: str, args: dict, at: int) -> dict:
    if type(seat) is not int or seat not in range(3):
        raise PresentationError(403, "Seat required")
    if room["status"] not in {"playing", "between", "awaiting_settlement"}:
        raise PresentationError(409, "No active table")
    p = state(control)
    if (
        type(args.get("presentation_version")) is not int
        or args["presentation_version"] != p["revision"]
    ):
        raise PresentationError(409, "Stale presentation version")
    rev = p["revision"] + 1
    desired = reasons(control)
    if action == "overlay_open":
        _keys(args, {"kind"})
        kind = args["kind"]
        if not isinstance(kind, str) or kind not in OVERLAYS:
            raise PresentationError(422, "Invalid overlay")
        if kind == "last_trick" and not (game and game.completed_tricks):
            raise PresentationError(409, "No completed trick")
        if kind == "widow_replay":
            if not (game and game.widow_revealed > 0):
                raise PresentationError(409, "No public widow")
            if not getattr(game, "is_passout", False) and (
                getattr(game, "trick", ()) or getattr(game, "completed_tricks", ())
            ):
                raise PresentationError(409, "Widow review ends with the first played card")
        if kind == "discard_replay" and not (
            game
            and game.declarer == seat
            and len(game.discarded) == 2
            and room["status"] == "playing"
        ):
            raise PresentationError(403, "Only the declarer may review the discard")
        p["overlay"] = {
            "kind": kind,
            "id": rev,
            "seat": seat,
            "game_id": room.get("game_id"),
            "opened_at_ms": at,
        }
        desired.add("shared_overlay")
    elif action == "overlay_close":
        _keys(args, {"overlay_id"})
        if (
            not p["overlay"]
            or type(args["overlay_id"]) is not int
            or args["overlay_id"] != p["overlay"]["id"]
        ):
            raise PresentationError(409, "Overlay changed")
        p["overlay"] = None
        desired.discard("shared_overlay")
    elif action == "break_start":
        _keys(args, set())
        if p["break"]:
            raise PresentationError(409, "Break already active")
        p["break"] = {"id": rev, "ready": [False, False, False]}
        desired.add("break")
    elif action == "break_ready":
        _keys(args, {"break_id", "ready"})
        pause = p["break"]
        if not pause or type(args["break_id"]) is not int or args["break_id"] != pause["id"]:
            raise PresentationError(409, "Break changed")
        if type(args["ready"]) is not bool:
            raise PresentationError(422, "Invalid readiness")
        presence = control.get("presence", [])
        if args["ready"] and (len(presence) != 3 or presence[seat] is None):
            raise PresentationError(409, "Connect before confirming")
        pause["ready"][seat] = args["ready"]
        if all(pause["ready"]) and all(v is not None for v in presence):
            p["break"] = None
            desired.discard("break")
    elif action == "music":
        _keys(args, {"command"})
        if not p["overlay"] or p["overlay"]["kind"] != "radio":
            raise PresentationError(409, "Open radio first")
        cmd = args["command"]
        track, offset = music_position(p["music"], at)
        playing = p["music"]["playing"]
        if cmd == "play":
            playing = True
        elif cmd == "pause":
            playing = False
        elif cmd == "stop":
            playing, offset = False, 0
        elif cmd in ("next", "previous"):
            track = (track + (1 if cmd == "next" else -1)) % TRACK_COUNT
            offset = 0
        else:
            raise PresentationError(422, "Invalid music command")
        p["music"] = {"track": track, "playing": playing, "offset_ms": offset, "changed_at_ms": at}
    else:
        raise PresentationError(422, "Invalid shared action")
    transition(control, desired, at)
    p["revision"] = rev
    return {"presentation_version": rev, "seat": seat}


def allows_replay_move(control: dict) -> bool:
    overlay = (control.get("presentation") or {}).get("overlay")
    return bool(
        overlay
        and overlay["kind"] == "last_trick"
        and reasons(control) == {"shared_overlay"}
        and not control.get("vote")
    )


def close_after_move(control: dict, at: int) -> None:
    if allows_replay_move(control):
        p = state(control)
        p["overlay"] = None
        p["revision"] += 1
        transition(control, reasons(control) - {"shared_overlay"}, at)


def invalidate_ready(control: dict, presence: list[int | None], interrupted: bool) -> list[dict]:
    p = control.get("presentation")
    pause = p.get("break") if p else None
    if not pause:
        return []
    ready = [
        value and not interrupted and presence[i] is not None
        for i, value in enumerate(pause["ready"])
    ]
    if ready == pause["ready"]:
        return []
    pause["ready"] = ready
    p["revision"] += 1
    return [{"action": "break_readiness_reset", "data": {"presentation_version": p["revision"]}}]
