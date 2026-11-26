"""Voluntary technical finish; never accept proposals from other players."""

from __future__ import annotations

ACTIONS = frozenset({"sheet_discard"})
ACTIVE = frozenset({"playing", "between", "awaiting_settlement"})


class SheetExitError(ValueError):
    def __init__(self, code: int, detail: str):
        super().__init__(detail)
        self.code = code


def change(
    control: dict, room: dict, seat: int, action: str, args: dict
) -> tuple[dict, int | None]:
    """Only the losing player can authorize the technical outcome."""
    if action not in ACTIONS:
        raise SheetExitError(422, "Invalid sheet action")
    if type(seat) is not int or seat not in range(3):
        raise SheetExitError(403, "Seat required")
    if room["status"] not in ACTIVE or None in room["seats"] or not room.get("game_id"):
        raise SheetExitError(409, "No active party")
    if set(args) != {"confirm"} or args["confirm"] is not True:
        raise SheetExitError(422, "Explicit confirmation required")
    return {"loser": seat, "source": "voluntary"}, seat


def finish(control: dict) -> None:
    """Stop the unfinished deal without changing the ledger or legacy data."""
    for key in ("timer", "vote", "candidate", "paused_at"):
        control[key] = None
    control["pause_reasons"] = []
    control.pop("next_deal", None)
    control.pop("sheet_offers", None)  # Remove retired pending proposals on terminal transition.
    control.pop("presentation", None)
