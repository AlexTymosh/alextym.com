"""Fast static regression checks for the Fleet VOR Hub UI corrections.

Run from the repository root. These checks supplement (do not replace)
`npm run typecheck` and `npm run build` inside frontend/.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "frontend" / "app" / "fleet-vor-hub"


def content(path: str) -> str:
    target = BASE / path
    assert target.is_file(), f"Missing {target}"
    return target.read_text(encoding="utf-8")


def verify() -> None:
    app = content("FleetApp.tsx")
    process = content("process/Panel.tsx")
    defect = content("new-defect/Panel.tsx")
    register = content("register/Panel.tsx")

    assert '"status-history"' in app
    assert 'registerExpanded' in app and 'styles.subnav' in app
    assert 'section==="dashboard"||section==="calendar"?section:"vehicles"' in app
    for label in ("Recorded Status History", "Add Vehicle", "Import Vehicles"):
        assert label in app

    for lane in ('name: "DRIVER"', 'name: "OSD / HOTH"', 'name: "PTS FLEET"', 'name: "GARAGE / SUPPLIER"'):
        assert lane in process
    assert 'name: "HOTH specialist"' not in process
    assert 'Roadside?' in process and 'Arrange recovery' in process
    assert 'Vehicle recovered' in process and 'After recovery' in process
    assert 'Vehicle back on road' in process and 'Manual KEY2 decision' in process
    assert 'AS-IS business process has not been formally mapped' in process
    for label in ("Outlook mailboxes", "Microsoft Teams groups", "Internal calendar", "Partner calendars", "KEY2 notes", "HOTH notes", "Multiple Excel files", "Telephone", "No RACI matrix", "No written procedures", "Duplicated effort"):
        assert label in process, label

    assert 'PROCESS CONTEXT' not in defect
    assert 'SYSTEM OF RECORD' not in defect
    assert 'Registration does not update KEY2 or send real' not in defect
    assert 'usual defect-handling process continues' in defect

    assert 'Download CSV template' in register and 'Registration,Model,Garage' in register
    assert '<th>Cases</th>' not in register and '<th>Action</th>' not in register
    assert '{section==="status-history"&&' in register
    assert '{section==="register"&&<section' in register
    assert 'Archive vehicle' in register and 'Restore vehicle' in register
    print('PASS: nested Vehicle Register, import template, AS-IS observations, 4-lane TO-BE, roadside rejoin, streamlined defect form')


if __name__ == "__main__":
    verify()
