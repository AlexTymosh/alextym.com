"""Read-only synthetic v2 management metrics. Never modifies fleet status."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import mean, median
from math import ceil


REQUIRED = 25


def _date(s: str):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _days(start, end):
    a, b = _date(start), _date(end)
    if a is None or b is None:
        return None
    if (a.tzinfo is None) != (b.tzinfo is None):
        a = a.replace(tzinfo=None)
        b = b.replace(tzinfo=None)
    return max(0, round((b - a).total_seconds() / 86400, 2))


def _pct(vals, q):
    if not vals:
        return None
    vals = sorted(vals)
    pos = (len(vals) - 1) * q
    low = int(pos)
    high = ceil(pos)
    return vals[low] + (vals[high] - vals[low]) * (pos - low)


def _dist(vals, exclude):
    original = len(vals)
    if exclude and len(vals) >= 4:
        q1, q3 = _pct(vals, 0.25), _pct(vals, 0.75)
        iqr = q3 - q1
        vals = [v for v in vals if q1 - 1.5 * iqr <= v <= q3 + 1.5 * iqr]
    return {
        "mean": round(mean(vals), 2) if vals else None,
        "median": round(median(vals), 2) if vals else None,
        "p90": round(_pct(vals, 0.9), 2) if vals else None,
        "retained": len(vals),
        "excluded": original - len(vals),
    }


def _table(db, name):
    return bool(
        db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    )


def report(
    start: str | None = None,
    end: str | None = None,
    garage: str | None = None,
    reason: str | None = None,
    model: str | None = None,
    exclude_outliers: bool = False,
):
    today = date.today().isoformat()
    end = end or today
    start = start or (date.today().replace(day=1)).isoformat()
    if start > end:
        raise ValueError("Start date must not be after end date")
    from fleet_hub.services import vor_data

    with vor_data.database() as db:
        db.row_factory = __import__("sqlite3").Row
        vehicles = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM vehicles WHERE COALESCE(is_archived,0)=0 ORDER BY id"
            )
        ]
        all_cases = (
            [dict(r) for r in db.execute("SELECT * FROM vor_cases ORDER BY opened_at,id")]
            if _table(db, "vor_cases")
            else []
        )
        status_events = (
            [
                dict(r)
                for r in db.execute("SELECT * FROM vor_status_events ORDER BY effective_at,id")
            ]
            if _table(db, "vor_status_events")
            else []
        )
        stats = (
            [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM dashboard_daily_stats WHERE date BETWEEN ? AND ? ORDER BY date",
                    (start, end),
                )
            ]
            if _table(db, "dashboard_daily_stats")
            else []
        )
        actions = (
            [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM ops_actions WHERE status='open' ORDER BY due_at,id"
                )
            ]
            if _table(db, "ops_actions")
            else []
        )
        blockers = (
            [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM ops_blockers WHERE status='active' ORDER BY created_at,id"
                )
            ]
            if _table(db, "ops_blockers")
            else []
        )
    vehicle_by_id = {v["id"]: v for v in vehicles}
    garages = sorted({str(v.get("garage") or "") for v in vehicles if v.get("garage")})
    reasons = sorted({str(c.get("vor_reason") or "Unspecified") for c in all_cases})
    models = sorted({str(v.get("model") or "") for v in vehicles if v.get("model")})
    selected = [
        v
        for v in vehicles
        if (not garage or v.get("garage") == garage) and (not model or v.get("model") == model)
    ]
    ids = {v["id"] for v in selected}
    cases = [
        c
        for c in all_cases
        if c["vehicle_id"] in ids
        and (not reason or c.get("vor_reason") == reason)
        and start <= str(c.get("opened_at", ""))[:10] <= end
    ]
    operational = sum(v["availability_status"] == "Operational" for v in selected)
    vor = sum(v["availability_status"] == "VOR" for v in selected)
    # Baseline requirement is meaningful only for whole-fleet scope.
    scoped = bool(garage or model or reason)
    diff = operational - REQUIRED if not scoped else None
    counts = Counter((c.get("vor_reason") or "Unspecified") for c in cases)
    closed = [c for c in cases if c.get("closed_at") and c.get("status") == "closed"]
    case_lengths = {c["id"]: _days(c["opened_at"], c["closed_at"]) for c in closed}
    valid = [v for v in case_lengths.values() if v is not None]
    completed_stats = _dist(valid, exclude_outliers)
    by_garage = defaultdict(list)
    for c in closed:
        dur = case_lengths[c["id"]]
        if dur is not None:
            by_garage[vehicle_by_id[c["vehicle_id"]].get("garage") or "Unassigned"].append(dur)
    workshops = [
        {"garage": k, "cases": len(v), **_dist(v, exclude_outliers)}
        for k, v in sorted(by_garage.items())
    ]
    # Source seed only has historical VOR and fleet counts, not historical deployment status.
    trend = (
        [
            {
                "date": d["date"],
                "fleet_count": d["fleet_count"],
                "vor": d["vor_count"],
                "non_vor_proxy": max(0, d["fleet_count"] - d["vor_count"]),
                "required": REQUIRED,
            }
            for d in stats
        ]
        if not scoped
        else []
    )
    open_actions = [a for a in actions if a["vehicle_id"] in ids]
    open_blockers = [b for b in blockers if b["vehicle_id"] in ids]
    overdue = [a for a in open_actions if str(a["due_at"])[:10] < today]
    report_cases = [
        {
            "registration": vehicle_by_id[c["vehicle_id"]]["registration"],
            "reason": c.get("vor_reason") or "Unspecified",
            "status": c.get("status"),
            "opened_at": c.get("opened_at"),
            "garage": vehicle_by_id[c["vehicle_id"]].get("garage"),
            "days": case_lengths.get(c["id"]),
        }
        for c in cases
    ]
    return {
        "as_of": today,
        "start": start,
        "end": end,
        "required": None if scoped else REQUIRED,
        "scope_warning": "Requirement 25 applies to the entire PTS fleet only; filtered numbers are not compared with it."
        if scoped
        else None,
        "vehicle_count": len(selected),
        "operational": operational,
        "vor": vor,
        "deviation": diff,
        "capacity_gap": max(0, -diff) if diff is not None else None,
        "counts_by_reason": [{"reason": k, "count": v} for k, v in counts.most_common()],
        "case_duration": completed_stats,
        "case_duration_basis": "Opened → closed VOR case; NOT independently measured garage labour/repair duration.",
        "open_cases": sum(c.get("status") == "open" for c in cases),
        "workshops": workshops,
        "trend": trend,
        "trend_note": "Historical non-VOR proxy = fleet_count − VOR. Not verified daily operational deployment; reference 25 is illustrative across that historical period.",
        "actions_open": len(open_actions),
        "overdue": len(overdue),
        "blockers": len(open_blockers),
        "cases": report_cases,
        "available_garages": garages,
        "available_reasons": reasons,
        "available_models": models,
        "daily_reporting_warning": "Daily report describes current status plus filtered case history; no historical deployment log or reliable repair start/end timestamps available.",
        "status_events_count": len(status_events),
        "outlier_method": "Tukey IQR: exclude values outside Q1−1.5×IQR to Q3+1.5×IQR, on completed cases only.",
    }
