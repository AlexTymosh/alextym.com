"""Pure, deterministic final game results and ranking projections.

No Firestore calls, clocks, hidden cards, player UIDs or browser state here.
The immutable ScoreState ledger remains authoritative for the final numbers.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .ledger import EntryKind, ScoreState
from .settlement import (
    discard_sheet_penalties,
    discard_sheet_placements,
    net_results,
    pair_punishments,
    placements,
)


def public_player_id(uid: str) -> str:
    """Stable opaque presentation key; never return Firebase UIDs in statistics."""
    if not isinstance(uid, str) or not uid or "/" in uid:
        raise ValueError("Invalid player identity")
    return hashlib.sha256(("preferans-result-v1:\0" + uid).encode()).hexdigest()[:24]


def placement_outcome(results: tuple[int, int, int], *, sheet_loser: int | None = None) -> dict:
    """Competition ranks; only a top pair receives two golds; a triple tie none."""
    if sheet_loser is None:
        ranks = placements(results)
        punches = pair_punishments(results)
    else:
        ranks = discard_sheet_placements(sheet_loser)
        punches = discard_sheet_penalties(sheet_loser)
    return {
        "places": list(ranks),
        "golds": [int(rank == 1) for rank in ranks],
        "silvers": [int(rank == 2) for rank in ranks],
        "thirds": [int(rank == 3) for rank in ranks],
        "technical_losses": [
            int(seat == sheet_loser) if sheet_loser is not None else 0 for seat in range(3)
        ],
        "punches": [
            {
                "from": award.winner,
                "to": award.loser,
                "bare": award.bare,
                "ordinary": award.ordinary,
            }
            for award in punches
        ],
    }


def final_result(
    room: dict, score: ScoreState, finished_ms: int, *, sheet_loser: int | None = None
) -> dict[str, Any]:
    """Snapshot final accounting, excluding unrevealed hands and Firebase UIDs."""
    if not score.closed and sheet_loser is None:
        raise ValueError("An incomplete game cannot enter the ranking")
    if type(finished_ms) is not int or finished_ms < 0:
        raise ValueError("Invalid server finish time")
    seats = room.get("seats")
    if not isinstance(seats, list) or len(seats) != 3 or None in seats or len(set(seats)) != 3:
        raise ValueError("A result requires exactly three distinct players")
    start = room.get("started_at_ms")
    if start is not None and (type(start) is not int or start > finished_ms or start < 0):
        raise ValueError("Invalid server-recorded start time")
    values = net_results(score) if sheet_loser is None else (0, 0, 0)
    outcome = placement_outcome(values, sheet_loser=sheet_loser)
    punches = outcome["punches"]
    entries = score.entries
    players = []
    for i, uid in enumerate(seats):
        bare_given = sum(p["bare"] for p in punches if p["from"] == i)
        bare_received = sum(p["bare"] for p in punches if p["to"] == i)
        ordinary_given = sum(p["ordinary"] for p in punches if p["from"] == i)
        ordinary_received = sum(p["ordinary"] for p in punches if p["to"] == i)
        players.append(
            {
                "id": public_player_id(uid),
                "seat": i,
                "net_vists": values[i],
                "place": outcome["places"][i],
                "gold": outcome["golds"][i],
                "silver": outcome["silvers"][i],
                "third": outcome["thirds"][i],
                "technical_losses": outcome["technical_losses"][i],
                "pool": score.pool[i],
                "hill": score.hill[i],
                "vists_given": sum(score.vists[i]),
                "vists_received": sum(row[i] for row in score.vists),
                "timer_hill": sum(
                    e.amount
                    for e in entries
                    if e.actor == i and e.kind == EntryKind.HILL and e.reason == "counter_180s"
                ),
                "bare_given": bare_given,
                "bare_received": bare_received,
                "ordinary_given": ordinary_given,
                "ordinary_received": ordinary_received,
            }
        )
    return {
        "schema_version": 1,
        "room_id": room["id"],
        "finished_at_ms": finished_ms,
        "started_at_ms": start,
        "duration_ms": finished_ms - start if start is not None else None,
        "active_ms": None,
        "reason": "sheet_discarded" if sheet_loser is not None else "pool_closed",
        "deal_count": score.version,
        "ruleset_hash": score.ruleset.sha256,
        "ruleset_version": score.ruleset.rules.version,
        "players": players,
        "punches": punches,
        "punches_confirmed": False,  # No player substitution choices in PR7 yet.
        "ledger_entry_count": len(entries),
        "ledger_sha256": hashlib.sha256(
            json.dumps(
                [
                    (e.sequence, e.deal_id, e.kind.value, e.actor, e.amount, e.reason, e.against)
                    for e in entries
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    }


_FIELDS = (
    "games",
    "gold",
    "silver",
    "third",
    "technical_losses",
    "net_vists",
    "vists_given",
    "vists_received",
    "timer_hill",
    "bare_given",
    "bare_received",
    "ordinary_given",
    "ordinary_received",
    "total_duration_ms",
    "timed_games",
)


def update_ranking(previous: dict | None, player: dict, result: dict) -> dict:
    """A materialized aggregate, updated once in the result-creation transaction."""
    if previous is not None and previous.get("id") != player["id"]:
        raise ValueError("Ranking document identity mismatch")
    base = {"id": player["id"], **{field: 0 for field in _FIELDS}}
    if previous is not None:
        for field in _FIELDS:
            value = previous.get(field)
            if type(value) is not int or value < 0 and field != "net_vists":
                raise ValueError("Corrupt materialized ranking")
            base[field] = value
    base["games"] += 1
    for field in _FIELDS:
        if field not in ("games", "total_duration_ms", "timed_games"):
            base[field] += player[field]
    if result["duration_ms"] is not None:
        base["total_duration_ms"] += result["duration_ms"]
        base["timed_games"] += 1
    base["last_finished_at_ms"] = max(
        (previous or {}).get("last_finished_at_ms", 0), result["finished_at_ms"]
    )
    return base
