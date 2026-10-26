"""Dependency-free structural smoke test for the unified Fleet VOR Hub UI."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'frontend/app/fleet-vor-hub'

def check() -> None:
    assert (ROOT/'frontend/app/fleet-vor-hub-01/page.tsx').is_file(), 'Frozen v1 UI missing'
    assert (ROOT/'backend/_local/vor_hub_01.sqlite3').is_file(), 'Frozen v1 DB missing'
    entry=(UI/'page.tsx').read_text(encoding='utf-8')
    assert 'from "./FleetApp"' in entry and '<FleetApp' in entry, 'Main route is still rendering legacy VorHub instead of FleetApp'
    shell=(UI/'FleetApp.tsx').read_text(encoding='utf-8')
    core=(UI/'VorHub.tsx').read_text(encoding='utf-8')
    styles=(UI/'vor.module.css').read_text(encoding='utf-8')
    assert 'export default function FleetApp()' in shell
    for view in ['workspace','dashboard','calendar','new-defect','register','add','import','process']:
        assert f'id:"{view}"' in shell, f'{view} missing from internal menu'
    assert 'onClick={()=>navigate(item.id)}' in shell
    assert 'styles.embeddedRoot' in core and '{!embedded&&<header' in core
    assert '.root.embeddedRoot{' in styles
    assert 'onAuthChange?.(true)' in core
    assert 'initialVehicle' in core
    for page in ['register','new-defect','process']:
        redirect=(UI/page/'page.tsx').read_text(encoding='utf-8')
        assert 'redirect("/fleet-vor-hub")' in redirect, page
        panel=(UI/page/'Panel.tsx').read_text(encoding='utf-8')
        assert 'from "next/link"' not in panel and '<Link' not in panel, page
        assert 'href=' not in panel, page
    register=(UI/'register/Panel.tsx').read_text(encoding='utf-8')
    assert 'section==="add"' in register and 'section==="import"' in register and 'section==="register"' in register
    process=(UI/'process/Panel.tsx').read_text(encoding='utf-8')
    for lane in ['Driver','OSD / HOTH','PTS Fleet','HOTH specialist','Garage / Supplier']:
        assert lane in process
    assert 'svg' in process.lower() and 'Roadside?' in process
    defect=(UI/'new-defect/Panel.tsx').read_text(encoding='utf-8')
    assert 'onRegistered?.(result.registration)' in defect
    assert 'next_action_owner' not in defect.lower() and 'next_action_deadline' not in defect.lower()
    print('PASS: single-route shell, eight internal sections, BPMN lanes, redirected legacy paths, independent frozen v1')

if __name__=='__main__':check()
