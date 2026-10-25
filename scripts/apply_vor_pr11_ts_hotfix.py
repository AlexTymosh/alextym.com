"""Fix PR-11 TypeScript TS2802 without changing the project's target or API.

Run from any folder: python scripts/apply_vor_pr11_ts_hotfix.py
"""
from __future__ import annotations

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend" / "app" / "fleet-vor-hub"
SOURCE = ROOT / "scripts" / "pr11_assets"
BACKUPS = ROOT / ".tmp" / "vor-pr11-ts-hotfix-backups"

PATCHES: dict[str, tuple[tuple[str, str], ...]] = {
    "CalendarBoard.tsx": (
        (
            "const bases=[...new Set(data.vehicles.map(v=>v.garage))].sort();",
            "const bases=Array.from(new Set(data.vehicles.map(v=>v.garage))).sort();",
        ),
        (
            "const partners=[...new Set(data.bookings.map(b=>b.garage))].sort();",
            "const partners=Array.from(new Set(data.bookings.map(b=>b.garage))).sort();",
        ),
    ),
    "DashboardPanel.tsx": (
        (
            "return [...counts].map(([label,count])=>({label,count})).sort((a,b)=>b.count-a.count);",
            "return Array.from(counts.entries()).map(([label,count])=>({label,count})).sort((a,b)=>b.count-a.count);",
        ),
    ),
    "OperationsQueuePanel.tsx": (
        (
            "const selected = [...new Map(tickets.map(x => [x.vehicle_id, x])).values()].slice(0, 8);",
            "const selected = Array.from(new Map(tickets.map(x => [x.vehicle_id, x])).values()).slice(0, 8);",
        ),
        (
            "setActivities([...new Map(rows.flat().map(a=>[`${a.vehicle}|${a.created_at}|${a.action}|${a.details}`,a])).values()].sort(",
            "setActivities(Array.from(new Map(rows.flat().map(a=>[`${a.vehicle}|${a.created_at}|${a.action}|${a.details}`,a])).values()).sort(",
        ),
        (
            "{[...new Set((displayExamples ? EXAMPLES : actions).map(item=>item.owner).filter(Boolean))].sort().map(owner=><option key={owner}>{owner}</option>)}",
            "{Array.from(new Set((displayExamples ? EXAMPLES : actions).map(item=>item.owner).filter((value): value is string => typeof value === \"string\" && value.length > 0))).sort().map(owner=><option key={owner} value={owner}>{owner}</option>)}",
        ),
    ),
}

FILES = {
    "CalendarBoard.tsx": FRONT / "calendar" / "CalendarBoard.tsx",
    "DashboardPanel.tsx": FRONT / "dashboard" / "DashboardPanel.tsx",
    "OperationsQueuePanel.tsx": FRONT / "operations" / "OperationsQueuePanel.tsx",
}


def verify_and_prepare(path: Path, patterns: tuple[tuple[str, str], ...]) -> tuple[str, str, int]:
    original = path.read_text(encoding="utf-8")
    updated = original
    changes = 0
    for old, new in patterns:
        old_count, new_count = updated.count(old), updated.count(new)
        if old_count == 1 and new_count == 0:
            updated = updated.replace(old, new, 1)
            changes += 1
        elif old_count == 0 and new_count == 1:
            pass  # already fixed
        else:
            raise RuntimeError(f"Unexpected source pattern in {path}: original={old_count}, fixed={new_count}, snippet={old[:65]!r}")
    return original, updated, changes


def main() -> int:
    paths = list(FILES.items()) + [(f"source/{name}", SOURCE / name) for name in FILES if (SOURCE / name).is_file()]
    planned = []
    for name, path in paths:
        if not path.is_file():
            raise RuntimeError(f"File not found: {path}. Install PR-11 first.")
        canonical_name = name.removeprefix("source/")
        original, updated, n = verify_and_prepare(path, PATCHES[canonical_name])
        planned.append((name, path, original, updated, n))
    # Validate all paths before mutating any files.
    for name, path, original, updated, count in planned:
        if count:
            backup = BACKUPS / ("source" if name.startswith("source/") else "frontend") / path.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(path, backup)
            path.write_text(updated, encoding="utf-8")
            print(f"Updated: {path.relative_to(ROOT)} ({count} replacement{'s' if count!=1 else ''})")
        else:
            print(f"Already fixed: {path.relative_to(ROOT)}")
    print("PASS: six PR-11 TS2802 patterns fixed without changing tsconfig or dependencies.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
