"""Voluntary technical finish. No financial settlement or opponent consent implied."""

from __future__ import annotations

ACTIONS = frozenset({"sheet_offer", "sheet_reply", "sheet_discard"})
ACTIVE = frozenset({"playing", "between", "awaiting_settlement"})


class SheetExitError(ValueError):
    def __init__(self, code: int, detail: str):
        super().__init__(detail)
        self.code = code


def current_offers(control: dict, room: dict) -> list[dict]:
    if room["status"] not in ACTIVE:
        return []
    return [
        {k: offer[k] for k in ("id", "from", "to")}
        for offer in control.get("sheet_offers", [])
        if offer["game_id"] == room.get("game_id")
    ]


def change(
    control: dict, room: dict, seat: int, action: str, args: dict
) -> tuple[dict, int | None]:
    """Only the losing player can authorize the technical outcome.

    One outstanding offer per recipient, bound to the current deal. The room
    CAS and operation key protect concurrent replies and retries.
    """
    if type(seat) is not int or seat not in range(3):
        raise SheetExitError(403, "Seat required")
    if room["status"] not in ACTIVE or None in room["seats"] or not room.get("game_id"):
        raise SheetExitError(409, "No active party")
    offers = current_offers(control, room)
    if action == "sheet_discard":
        if set(args) != {"confirm"} or args["confirm"] is not True:
            raise SheetExitError(422, "Explicit confirmation required")
        return {"loser": seat, "source": "voluntary"}, seat
    if action == "sheet_offer":
        target = args.get("target")
        if (
            set(args) != {"target"}
            or type(target) is not int
            or target not in range(3)
            or target == seat
        ):
            raise SheetExitError(422, "Invalid offer recipient")
        if any(offer["to"] == target for offer in offers):
            raise SheetExitError(409, "Recipient already has an offer")
        offer = {"id": room["version"] + 1, "from": seat, "to": target}
        control["sheet_offers"] = [
            {**item, "game_id": room["game_id"]} for item in [*offers, offer]
        ]
        return offer.copy(), None
    if action == "sheet_reply":
        if (
            set(args) != {"offer_id", "accept"}
            or type(args["offer_id"]) is not int
            or type(args["accept"]) is not bool
        ):
            raise SheetExitError(422, "Invalid reply")
        offer = next((item for item in offers if item["id"] == args["offer_id"]), None)
        if offer is None or offer["to"] != seat:
            raise SheetExitError(409, "No matching offer for this seat")
        control["sheet_offers"] = [
            {**item, "game_id": room["game_id"]} for item in offers if item["id"] != offer["id"]
        ]
        event = {**offer, "accepted": args["accept"]}
        if args["accept"]:
            return {**event, "loser": seat, "source": "accepted"}, seat
        return event, None
    raise SheetExitError(422, "Invalid sheet action")


def finish(control: dict) -> None:
    """Stop the unfinished deal without changing the ledger or legacy data."""
    for key in ("timer", "vote", "candidate", "paused_at"):
        control[key] = None
    control["pause_reasons"] = []
    control.pop("next_deal", None)
    control.pop("sheet_offers", None)
    # Presentation is no longer projected for a terminal room.
    control.pop("presentation", None)
