"""One-time, idempotent PR-03 integration on top of PR-02.

Run at repository root after extracting PR-03 files. Refuses mismatched versions.
Does not touch the frozen Fleet VOR Hub v1 sources, API, SQLite, or email flags.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "backend/app/main.py"
UI = ROOT / "frontend/app/fleet-vor-hub/VorHub.tsx"
VOR_DATA = ROOT / "backend/app/services/vor_data.py"
STORE = ROOT / "backend/app/services/vor_store.py"


def patch(path: Path, original: str, replacement: str) -> None:
    contents = path.read_text(encoding="utf-8")
    if replacement in contents:
        print("Already patched:", path.relative_to(ROOT))
        return
    if contents.count(original) != 1:
        raise RuntimeError(
            f"Cannot locate unique patch point in {path.relative_to(ROOT)}; "
            "verify PR-02 was installed and the working tree is clean."
        )
    path.write_text(contents.replace(original, replacement, 1), encoding="utf-8", newline="\n")
    print("Updated:", path.relative_to(ROOT))


def main() -> None:
    for path in [
        ROOT / "backend/app/services/vor_store_v1.py",
        ROOT / "backend/app/api/vor_v1.py",
        ROOT / "frontend/app/fleet-vor-hub-01/page.tsx",
        ROOT / "backend/app/services/vor_data.py",
        ROOT / "backend/app/api/vor_data.py",
        ROOT / "backend/app/services/vor_intake.py",
        ROOT / "backend/app/api/vor_intake.py",
    ]:
        if not path.is_file():
            raise RuntimeError(f"Required PR-01/02/03 file missing: {path.relative_to(ROOT)}")
    if not (ROOT / "backend/_local/vor_hub_01.sqlite3").is_file():
        raise RuntimeError("Frozen v1 SQLite is missing — stop before changing v2")
    # The PR-02 register inserts must use a valid status in the real seeded DB.
    # Its CHECK constraint accepts 'Operational' and 'VOR', not 'Available'.
    patch(
        VOR_DATA,
        '"availability_status": "Available", "severity": "Low", "issue": "No active defect",',
        '"availability_status": "Operational", "severity": "Low", "issue": "No active defect",',
    )
    patch(VOR_DATA, '_status_baseline(db,vehicle_id,"Available")', '_status_baseline(db,vehicle_id,"Operational")')
    patch(
        VOR_DATA,
        '"odometer_miles": 0, "unread_count": 0, "is_archived": 0,',
        '"odometer_miles": 0, "unread_count": 0, "is_archived": 0, "last_service_date": date.today().isoformat(),',
    )
    patch(
        VOR_DATA,
        'if status not in {"VOR","Available"}:',
        'if status not in {"VOR","Operational"}:',
    )
    patch(
        VOR_DATA,
        '"UPDATE vehicles SET availability_status=?,vor_days=CASE WHEN ?=\'Available\' THEN 0 ELSE vor_days END WHERE id=?",',
        '"UPDATE vehicles SET availability_status=?,vor_days=CASE WHEN ?=\'Operational\' THEN 0 ELSE vor_days END WHERE id=?",',
    )
    test_data = ROOT / "backend/tests/test_vor_data_foundation.py"
    if test_data.exists():
        for old, new in [
            ('vor_data.update_status(1, "Available",', 'vor_data.update_status(1, "Operational",'),
            ('vor_data.update_status(1,"Available",', 'vor_data.update_status(1,"Operational",'),
            ('== "Available"', '== "Operational"'),
        ]:
            text = test_data.read_text(encoding="utf-8")
            if old in text:
                test_data.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
                print("Updated fixture:", test_data.relative_to(ROOT))
    patch(
        MAIN,
        'from app.api.vor_data import router as vor_data_router\n',
        'from app.api.vor_data import router as vor_data_router\nfrom app.api.vor_intake import router as vor_intake_router\n',
    )
    patch(
        MAIN,
        '    app.include_router(vor_data_router, prefix="/api")\n',
        '    app.include_router(vor_data_router, prefix="/api")\n    app.include_router(vor_intake_router, prefix="/api")\n',
    )
    patch(
        UI,
        '<a className={styles.exportButton} href="/fleet-vor-hub/register" title="Vehicle register and imports">Vehicle Register</a>',
        '<a className={styles.exportButton} href="/fleet-vor-hub/register" title="Vehicle register and imports">Vehicle Register</a><a className={styles.exportButton} href="/fleet-vor-hub/new-defect" title="Register OSD / HOTH notification">+ New Defect</a><a className={styles.exportButton} href="/fleet-vor-hub/process" title="AS-IS and TO-BE process mapping">Process Design</a>',
    )
    patch(
        UI,
        ' const selected=data?.vehicles.find(v=>v.registration===reg)||data?.vehicles[0];',
        ' useEffect(()=>{const requested=new URLSearchParams(window.location.search).get("vehicle");if(requested)setReg(requested);},[]);\n const selected=data?.vehicles.find(v=>v.registration===reg)||data?.vehicles[0];',
    )
    # Specialist HOTH cases cannot accidentally be converted into PTS-owned workflows.
    patch(
        STORE,
        '        if ticket["status"] != "open":\n            raise ValueError("Only open tickets can change scenario")',
        '        if ticket["status"] != "open":\n            raise ValueError("Only open tickets can change scenario")\n        if db.execute("SELECT 1 FROM vor_cases WHERE legacy_ticket_id=? AND pathway IN (\'tyres\',\'windscreen\')", (ticket_id,)).fetchone():\n            raise ValueError("Specialist repairs are managed by the HOTH team")',
    )
    notes = ROOT / "Session_Notes.md"
    if notes.exists():
        marker = "### Session 2026-10-20 — PR-03 Process Design and Defect Intake"
        content = notes.read_text(encoding="utf-8")
        if marker not in content:
            with notes.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write("\n" + marker + "\n\n")
                handle.write("- **Scope:** v2-only AS-IS/TO-BE process diagram and separate New Defect form.\n")
                handle.write("- **Defect intake:** HOTH reference, vehicle, pathway, VOR reason, observations; no action owner/deadline fields.\n")
                handle.write("- **Workflow:** Standard Defect gets the eight-stage template; HOTH-owned specialist cases have no PTS stages.\n")
                handle.write("- **Status:** reported VOR does not alter KEY2/vehicle availability; release remains manual.\n")
                handle.write("- **PR-02 compatibility:** corrected Operational status and last_service_date for real seeded SQLite.\n")
                handle.write("- **Verification gate G2:** targeted pytest, frontend build, browser review and v1 isolation check pending.\n")
    print("PR-03 integration complete. Frozen v1 source and SQLite were not edited.")


if __name__ == "__main__":
    main()
