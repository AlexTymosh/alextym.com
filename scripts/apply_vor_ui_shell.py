"""Integrate the single-route Fleet VOR Hub app shell on top of PR-03.

Run from the repository root after extracting this zip. Only changes the v2
VorHub component and CSS; frozen /fleet-vor-hub-01 is never touched.
Idempotent: a second invocation reports Already patched without duplicating code.
"""
from __future__ import annotations

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'frontend/app/fleet-vor-hub/VorHub.tsx'
CSS=ROOT/'frontend/app/fleet-vor-hub/vor.module.css'
NOTES=ROOT/'Session_Notes.md'

PATCHES=[
 ('export default function VorHub() {',
  'export default function VorHub({embedded=false,externalView,initialVehicle,onAuthChange}:{embedded?:boolean;externalView?:Tab;initialVehicle?:string|null;onAuthChange?:(authenticated:boolean)=>void}={}) {'),
 (' const [reg,setReg]=useState<string>("GX24 KLM");const [search,setSearch]=useState("");',
  ' const [reg,setReg]=useState<string>("GX24 KLM");const [search,setSearch]=useState("");\n useEffect(()=>{if(externalView)setView(externalView)},[externalView]);\n useEffect(()=>{if(initialVehicle)setReg(initialVehicle)},[initialVehicle]);'),
 ('setSession(s);if(s.authenticated) load().catch',
  'setSession(s);onAuthChange?.(s.authenticated);if(s.authenticated) load().catch'),
 ('setSession(x=>({...x!,authenticated:true}));setPassword("");',
  'setSession(x=>({...x!,authenticated:true}));onAuthChange?.(true);setPassword("");'),
 ('return <div className={styles.root}>\n  <header className={styles.header}>',
  'return <div className={`${styles.root} ${embedded?styles.embeddedRoot:""}`}>\n  {!embedded&&<header className={styles.header}>'),
 ('</header>\n  {notice&&',
  '</header>}\n  {notice&&'),
]
CSS_ADD='\n/* Embedded in the single-route FleetApp shell; frozen v1 is untouched. */\n.root.embeddedRoot{position:relative;inset:auto;z-index:auto;width:100%;height:100%;min-height:0;overflow:hidden;}\n'


def main()->None:
    required=[
      ROOT/'backend/app/services/vor_store_v1.py',
      ROOT/'frontend/app/fleet-vor-hub-01/page.tsx',
      ROOT/'frontend/app/fleet-vor-hub/FleetApp.tsx',
      ROOT/'frontend/app/fleet-vor-hub/register/Panel.tsx',
      ROOT/'frontend/app/fleet-vor-hub/new-defect/Panel.tsx',
      ROOT/'frontend/app/fleet-vor-hub/process/Panel.tsx',
    ]
    for path in required:
        if not path.is_file():raise RuntimeError(f'Missing required file: {path.relative_to(ROOT)}')
    if not (ROOT/'backend/_local/vor_hub_01.sqlite3').is_file():
        raise RuntimeError('Frozen v1 SQLite missing: stop before changing v2')
    if not UI.is_file() or not CSS.is_file():
        raise RuntimeError('v2 VorHub.tsx / vor.module.css missing')
    original=UI.read_text(encoding='utf-8')
    updated=original
    for before,after in PATCHES:
        if after in updated:
            continue
        occurrences=updated.count(before)
        if occurrences!=1:
            raise RuntimeError(f'Unsupported VorHub.tsx version or incomplete PR-03: expected 1 occurrence of {before[:75]!r}, found {occurrences}. No changes were written.')
        updated=updated.replace(before,after,1)
    css=CSS.read_text(encoding='utf-8')
    if '.root.embeddedRoot{' not in css:css+=CSS_ADD
    # All validations are complete. Only now write v2 files.
    if updated!=original:
        UI.write_text(updated,encoding='utf-8',newline='\n')
        print('Updated:',UI.relative_to(ROOT))
    else:
        print('Already patched:',UI.relative_to(ROOT))
    if css!=CSS.read_text(encoding='utf-8'):
        CSS.write_text(css,encoding='utf-8',newline='\n')
        print('Updated:',CSS.relative_to(ROOT))
    else:
        print('Already patched:',CSS.relative_to(ROOT))
    marker='### Session 2026-10-21 — Unified app shell and BPMN swimlanes'
    if NOTES.exists():
        text=NOTES.read_text(encoding='utf-8')
        if marker not in text:
            with NOTES.open('a',encoding='utf-8',newline='\n') as file:
                file.write('\n'+marker+'\n\n')
                file.write('- **UI:** /fleet-vor-hub is one state-driven app with a collapsible Odoo-inspired sidebar; no navigation between Next.js pages.\n')
                file.write('- **Fleet data:** Vehicle Register, Add Vehicle and Import Vehicles are separate app sections (same working API).\n')
                file.write('- **Defects:** New Defect is a distinct internal section; no Next Action owner/deadline fields.\n')
                file.write('- **BPMN:** Visio-style horizontal swimlanes with SCAS roles and external Garage/Supplier, AS-IS/TO-BE tabs.\n')
                file.write('- **Compatibility:** existing v2 Workspace, Dashboard, Calendar, Excel export, login and backend APIs preserved.\n')
                file.write('- **Legacy paths:** /register, /new-defect, /process redirect to /fleet-vor-hub. Frozen v1 unaffected.\n')
                file.write('- **Verification:** run npm run typecheck and npm run build; manual browser checks on all eight app sections.\n')
    print('Unified Fleet VOR Hub integration complete; frozen v1 and both SQLite files unchanged.')

if __name__=='__main__':main()
