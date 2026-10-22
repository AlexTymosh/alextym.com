"""Read-only structural smoke checks for PR07."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
m=(R/'backend/app/main.py').read_text(encoding='utf-8');v=(R/'frontend/app/fleet-vor-hub/VorHub.tsx').read_text(encoding='utf-8')
checks=[('router import','from app.api.vor_reporting import router as vor_reporting_router' in m),('router mount','app.include_router(vor_reporting_router, prefix="/api")' in m),('dashboard import','import ManagementDashboard' in v),('dashboard visible','<ManagementDashboard/>' in v),('frozen v1',(R/'backend/app/services/vor_store_v1.py').is_file()),('report logic',(R/'backend/app/services/vor_reporting.py').is_file())]
for name,ok in checks:print(('PASS' if ok else 'FAIL'),name)
if not all(v for _,v in checks):raise SystemExit(1)
