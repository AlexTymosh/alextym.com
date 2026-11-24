"""Unanimous seat changes before the first deal; no identity data in events."""

from __future__ import annotations

ACTIONS = frozenset({"seat_swap_offer", "seat_swap_vote"})


class SeatSwapError(ValueError):
    def __init__(self, code: int, detail: str):
        super().__init__(detail)
        self.code = code


def is_seat(value: object) -> bool:
    return type(value) is int and value in range(3)


def pending(room: dict) -> dict | None:
    if room.get("status") != "lobby":
        return None
    return room.get("seat_swap")


def projection(room: dict) -> dict | None:
    offer = pending(room)
    if offer is None:
        return None
    return {
        "id": offer["id"],
        "from": offer["from"],
        "to": offer["to"],
        "votes": list(offer["votes"]),
    }


def change(room: dict, control: dict, seat: int, action: str, args: dict) -> tuple[dict, bool]:
    """Mutate transactional copies only; the final voter applies the permutation."""
    if not is_seat(seat):
        raise SeatSwapError(403, "Seat required")
    setup = room.get("lobby_setup")
    seats = room.get("seats")
    if (
        room.get("status") != "lobby"
        or room.get("game_id") is not None
        or not isinstance(setup, dict)
        or not isinstance(seats, list)
        or len(seats) != 3
        or not all(isinstance(uid, str) and uid for uid in seats)
        or len(set(seats)) != 3
    ):
        raise SeatSwapError(409, "Seat changes require a full new lobby")
    offer = pending(room)
    if action == "seat_swap_offer":
        if set(args) != {"to"} or not is_seat(args["to"]) or args["to"] == seat:
            raise SeatSwapError(422, "Invalid target seat")
        if offer is not None:
            raise SeatSwapError(409, "Seat change already pending")
        votes = [False, False, False]
        votes[seat] = True
        offer = {"id": room["version"] + 1, "from": seat, "to": args["to"], "votes": votes}
        room["seat_swap"] = offer
        return {"id": offer["id"], "from": seat, "to": args["to"]}, False
    if action != "seat_swap_vote" or set(args) != {"id", "approve"}:
        raise SeatSwapError(422, "Invalid seat change command")
    if type(args["id"]) is not int or type(args["approve"]) is not bool:
        raise SeatSwapError(422, "Invalid seat change vote")
    if offer is None or offer["id"] != args["id"]:
        raise SeatSwapError(409, "Seat change expired")
    event = {
        "id": offer["id"],
        "from": offer["from"],
        "to": offer["to"],
        "approved": args["approve"],
    }
    if not args["approve"]:
        room.pop("seat_swap", None)
        return {**event, "outcome": "refused"}, False
    if offer["votes"][seat]:
        raise SeatSwapError(409, "Vote already recorded")
    offer["votes"][seat] = True
    if not all(offer["votes"]):
        return {**event, "outcome": "pending"}, False
    a, b = offer["from"], offer["to"]
    dealer_uid = seats[setup["dealer"]]
    seats[a], seats[b] = seats[b], seats[a]
    setup["dealer"] = seats.index(dealer_uid)
    setup["ready"] = [False, False, False]
    control["presence"] = [None, None, None]
    room["seat_revision"] = room.get("seat_revision", 0) + 1
    room.pop("seat_swap", None)
    return {**event, "outcome": "swapped", "seat_revision": room["seat_revision"]}, True
