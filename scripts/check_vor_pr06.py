"""Static smoke check after PR-06 integration (not a substitute for runtime tests)."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
main=(root/'backend/app/main.py').read_text(encoding='utf-8')
shell=(root/'frontend/app/fleet-vor-hub/FleetApp.tsx').read_text(encoding='utf-8')
assert 'app.include_router(vor_reconciliation_router, prefix="/api")' in main
assert 'reconciliation:"Reconciliation"' in shell
assert 'section==="reconciliation"&&<ReconciliationPanel/>' in shell
assert 'import ReconciliationPanel' in shell
assert 'id:"reconciliation"' in shell
assert (root/'frontend/app/fleet-vor-hub-01/page.tsx').exists()
assert (root/'backend/app/services/vor_store_v1.py').exists()
print('PASS: PR-06 reconciliation integration, v2-only endpoints and single-route menu')
