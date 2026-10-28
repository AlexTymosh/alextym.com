"""Repair and diagnose the /fleet-vor-hub single-route entrypoint.

Only changes frontend/app/fleet-vor-hub/page.tsx if it still renders
legacy VorHub. Neither API nor databases are modified.
Run from repository root: python scripts/repair_vor_ui_entry.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "frontend" / "app" / "fleet-vor-hub"
ENTRY = UI / "page.tsx"
PANELS = {
    "Vehicle Register / Add Vehicle / Import Vehicles": UI / "register" / "Panel.tsx",
    "New Defect": UI / "new-defect" / "Panel.tsx",
    "Process Design (BPMN)": UI / "process" / "Panel.tsx",
}


def repair() -> int:
    required = {
        "main entrypoint": ENTRY,
        "unified app shell": UI / "FleetApp.tsx",
        **PANELS,
    }
    missing = [name + ": " + str(path.relative_to(ROOT)) for name, path in required.items() if not path.is_file()]
    if missing:
        print("ERROR: Required files are missing:\n  " + "\n  ".join(missing))
        return 2
    entry = ENTRY.read_text(encoding="utf-8")
    if 'from "./FleetApp"' in entry and '<FleetApp' in entry:
        print("OK: /fleet-vor-hub already renders FleetApp (unified menu).")
    elif 'from "./VorHub"' in entry and '<VorHub' in entry:
        updated = entry.replace('from "./VorHub"', 'from "./FleetApp"', 1).replace('<VorHub', '<FleetApp', 1)
        if updated == entry or 'from "./FleetApp"' not in updated or '<FleetApp' not in updated:
            print("ERROR: Unexpected entrypoint content; no changes made.")
            return 2
        ENTRY.write_text(updated, encoding="utf-8", newline="\n")
        print("FIXED: /fleet-vor-hub entrypoint now renders FleetApp with internal navigation.")
    else:
        print("ERROR: page.tsx does not match the expected old or new entrypoint; no changes made.")
        print("Inspect frontend/app/fleet-vor-hub/page.tsx manually.")
        return 2
    shell = (UI / "FleetApp.tsx").read_text(encoding="utf-8")
    expected = ('workspace','dashboard','calendar','new-defect','process','register','add','import')
    absent = [view for view in expected if 'id:"' + view + '"' not in shell]
    if absent:
        print("ERROR: These internal sections are missing from FleetApp:", ', '.join(absent))
        return 2
    for label in PANELS:
        print("OK:", label)
    print("OK: All eight active app sections declared.")
    return 0


if __name__ == "__main__":
    sys.exit(repair())
