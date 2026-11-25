"""One immutable election per directed pair; final accounting stays unchanged."""

from __future__ import annotations

from copy import deepcopy


def initial(result: dict) -> list[dict]:
    return [{**p, "replacement": None} for p in result["punches"] if p["bare"]]


def choose(pairs: list[dict], seat: int, args: dict) -> tuple[dict, int]:
    if (
        set(args) != {"from", "replace"}
        or type(args["from"]) is not int
        or type(args["replace"]) is not int
    ):
        raise ValueError("Invalid choice")
    pair = next((p for p in pairs if p["from"] == args["from"] and p["to"] == seat), None)
    if pair is None or pair["replacement"] is not None:
        raise ValueError("No undecided pair for this player")
    count = args["replace"]
    if not 0 <= count <= pair["bare"]:
        raise ValueError("Replacement outside calculated allowance")
    pair["replacement"] = count
    return {"from": pair["from"], "to": seat, "replacement": count}, count


def ranking_delta(ranking: dict, side: str, count: int) -> dict:
    if side not in ("given", "received") or type(count) is not int or count < 0:
        raise ValueError("Invalid replacement delta")
    result = dict(ranking)
    bare, ordinary = "bare_" + side, "ordinary_" + side
    if (
        type(result.get(bare)) is not int
        or result[bare] < count
        or type(result.get(ordinary)) is not int
    ):
        raise ValueError("Corrupt ranking")
    result[bare] -= count
    result[ordinary] += 10 * count
    return result


def effective(result: dict, pairs: list[dict]) -> dict:
    """Read-side projection, never mutate the immutable stored result."""
    view = deepcopy(result)
    for choice in pairs:
        count = choice["replacement"]
        if count is None:
            continue
        winner, loser = choice["from"], choice["to"]
        award = next(p for p in view["punches"] if p["from"] == winner and p["to"] == loser)
        award["bare"] -= count
        award["ordinary"] += 10 * count
        for player in view["players"]:
            if player["seat"] == winner:
                player["bare_given"] -= count
                player["ordinary_given"] += 10 * count
            if player["seat"] == loser:
                player["bare_received"] -= count
                player["ordinary_received"] += 10 * count
    view["punches_confirmed"] = all(p["replacement"] is not None for p in pairs)
    view["punch_choices"] = deepcopy(pairs)
    return view
