"""Integrate reporting without modifying frozen v1. Rerunnable. Run from repo root."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
MAIN=R/'backend/app/main.py';VIEW=R/'frontend/app/fleet-vor-hub/VorHub.tsx';NOTES=R/'Session_Notes.md'

def once(s,old,new,name):
    if new in s:return s
    if s.count(old)!=1:raise RuntimeError(f'{name} anchor found {s.count(old)} times; no changes written')
    return s.replace(old,new,1)

def main():
    for f in [MAIN,VIEW,R/'backend/app/services/vor_reporting.py',R/'backend/app/api/vor_reporting.py',R/'frontend/app/fleet-vor-hub/dashboard/DashboardPanel.tsx',R/'backend/app/services/vor_store_v1.py']:
        if not f.is_file():raise RuntimeError(f'Missing prerequisite: {f}')
    s=MAIN.read_text(encoding='utf-8');v=VIEW.read_text(encoding='utf-8')
    s=once(s,'from app.api.vor import router as vor_router','from app.api.vor import router as vor_router\nfrom app.api.vor_reporting import router as vor_reporting_router','reporting import')
    s=once(s,'    app.include_router(vor_router, prefix="/api")','    app.include_router(vor_router, prefix="/api")\n    app.include_router(vor_reporting_router, prefix="/api")','reporting router mount')
    v=once(v,'import styles from "./vor.module.css";','import styles from "./vor.module.css";\nimport ManagementDashboard from "./dashboard/DashboardPanel";','dashboard import')
    v=once(v,'{view==="dashboard"?<Dashboard data={data}/>:', '{view==="dashboard"?<ManagementDashboard/>:', 'dashboard rendering')
    if MAIN.read_text(encoding='utf-8')!=s:MAIN.write_text(s,encoding='utf-8',newline='\n');print('Updated:', MAIN.relative_to(R))
    if VIEW.read_text(encoding='utf-8')!=v:VIEW.write_text(v,encoding='utf-8',newline='\n');print('Updated:',VIEW.relative_to(R))
    heading='### PR-07 — Management Dashboard'
    if NOTES.is_file() and heading not in NOTES.read_text(encoding='utf-8'):
        with NOTES.open('a',encoding='utf-8',newline='\n') as out:out.write('\n'+heading+'\n\n- Whole-fleet baseline requirement 25, current operational count and difference.\n- Date/model/garage/reason filters; scoped metrics do not inherit whole-fleet requirement.\n- Completed case duration mean/median/P90; IQR transparency; not equivalent to measured garage repair time.\n- Historical non-VOR proxy explicitly labelled, not actual vehicle deployments.\n- Cases by reason; workshop completed-case comparison; actions and blockers; CSV report.\n- No writes to vehicles, status history or frozen v1.\n- Validation: backend tests, frontend typecheck/build and browser smoke test remain required.\n')
    print('PR-07 integrated; frozen v1 unchanged.')
if __name__=='__main__':main()
