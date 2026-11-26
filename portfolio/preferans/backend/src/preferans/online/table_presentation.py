"""Numeric-only notebook history and lobby naming helpers."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def room_day(at_ms: int) -> str:
    return (
        datetime.fromtimestamp(at_ms / 1000, timezone.utc)
        .astimezone(ZoneInfo("Europe/London"))
        .date()
        .isoformat()
    )


def notebook(score, controls: dict) -> dict:
    """Project immutable ledger entries; never guess missing legacy corrections.

    Each cell is a sequence of running balances. The final value is authoritative.
    New manual corrections are merged at their ledger position. Old corrections
    without an ordering marker are explicitly identified as incomplete.
    """
    keys = [(kind, i, None) for kind in ("hill", "pool") for i in range(3)]
    keys += [("vist", i, j) for i in range(3) for j in range(3) if i != j]
    cells = {key: [] for key in keys}
    current = dict.fromkeys(keys, 0)
    exact = not controls.get("score_sheet_legacy", False)
    marks = []
    latest = None

    def record(key, delta, manual=False):
        nonlocal exact, latest
        if key not in current:
            exact = False
            return
        current[key] += delta
        cells[key].append(current[key])
        latest = {"field": key[0], "seat": key[1], "against": key[2], "index": len(cells[key]) - 1}
        if manual:
            marks.append({**latest, "manual": True})

    corrections = controls.get("score_sheet_adjustments", [])
    legacy = controls.get("adjustments", [])
    recorded = {item["game_version"] for item in corrections}
    if any(item["game_version"] not in recorded for item in legacy):
        exact = False
    by_sequence = {}
    for item in corrections:
        by_sequence.setdefault(item["ledger_sequence"], []).append(item)

    def apply_corrections(sequence):
        for item in by_sequence.get(sequence, []):
            key = (item["field"], item["seat"], item["against"])
            record(key, item["delta"], manual=True)

    apply_corrections(0)
    for entry in score.entries:
        kind = entry.kind.value
        key = ("hill" if kind == "hill_payment" else kind, entry.actor, entry.against)
        record(key, -entry.amount if kind == "hill_payment" else entry.amount)
        apply_corrections(entry.sequence)
    for key in keys:
        kind, i, j = key
        final = (
            score.hill[i]
            if kind == "hill"
            else score.pool[i]
            if kind == "pool"
            else score.vists[i][j]
        )
        if current[key] != final:
            exact = False
            cells[key].append(final)
    # On old corrected sheets, the old entries may not be chronological running
    # balances. Show only authoritative totals rather than invent a history.
    if not exact:
        for kind, i, j in keys:
            final = (
                score.hill[i]
                if kind == "hill"
                else score.pool[i]
                if kind == "pool"
                else score.vists[i][j]
            )
            cells[kind, i, j] = [final] if final else []
    if exact and latest is not None:
        for mark in marks:
            if all(mark[k] == latest[k] for k in latest):
                mark["latest"] = True
                break
        else:
            marks.append({**latest, "latest": True})
    return {
        "exact": exact,
        "marks": marks if exact else [],
        "hill": [cells["hill", i, None] for i in range(3)],
        "pool": [cells["pool", i, None] for i in range(3)],
        "vists": [[cells.get(("vist", i, j), []) for j in range(3)] for i in range(3)],
    }
