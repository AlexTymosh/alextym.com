"""Smoke check the v2-only visual refinements from the repo root."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'frontend/app/fleet-vor-hub'
checks={
 'FleetApp.tsx': ['Local demonstration · synthetic data','Recorded Status History'],
 'VorHub.tsx': ['SECTION_WORKFLOW_MOVED','WORKFLOW_ITEMS','styles.calendarFilters','styles.stageChecklist','/checklists/advance'],
 'process/Panel.tsx': ['onPointerDown','Reset layout','Return to service'],
 'new-defect/Panel.tsx': ['name="vor-reason"','useState("")','styles.reasonGrid'],
 'register/Panel.tsx': ['Recorded status','local synthetic audit history'],
 'vor.module.css': ['v2 UX refinement: calendar filters + right-side checklist'],
}
for file, terms in checks.items():
 p=base/file
 if not p.exists():raise SystemExit(f'MISSING {p}')
 text=p.read_text(encoding='utf-8')
 for term in terms:
  if term not in text:raise SystemExit(f'MISSING {file} => {term}')
main=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
if 'vor_checklist_router' not in main:raise SystemExit('Checklist router not mounted')
if not (ROOT/'frontend/app/fleet-vor-hub-01/page.tsx').is_file():raise SystemExit('Frozen v1 missing')
if not (ROOT/'backend/_local/vor_hub_01.sqlite3').is_file():raise SystemExit('Frozen v1 database missing')
print('PASS: unified v2 refinements, calendar, persisted checklist router, frozen v1 present')
