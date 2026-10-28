"""Structural smoke checks after applying PR-04/05.

These do NOT replace local pytest, Next.js typecheck/build, or browser tests.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def require(path:str, markers:list[str]):
    item=ROOT/path
    if not item.is_file():raise SystemExit(f'FAIL: {path} does not exist')
    value=item.read_text(encoding='utf-8')
    for marker in markers:
        if marker not in value:raise SystemExit(f'FAIL: {path} missing {marker[:50]}')

require('backend/app/main.py',['vor_operations_router','app.include_router(vor_operations_router'])
require('backend/app/services/vor_operations.py',['ops_actions','ops_blockers','ops_documents','ops_release_checks','vor_status_events','ops_stage_settings'])
require('backend/app/api/vor_operations.py',['/overview','/queue','/skip','/status','/templates'])
require('backend/app/api/vor_checklist.py',['ops.required_keys(db,index)'])
require('backend/app/api/vor.py',['advance_with_checks(AdvanceStage('])
require('backend/app/services/vor_store.py',['for table_name in ("vor_step_checklists"'])
require('frontend/app/fleet-vor-hub/VorHub.tsx',['OperationsPanel','AssetSignals','opsOverview','configuredStages'])
require('frontend/app/fleet-vor-hub/FleetApp.tsx',['WorkflowSettingsPanel','OperationsQueuePanel','operations-queue'])
for file in ('OperationsPanel.tsx','WorkflowSettingsPanel.tsx','OperationsQueuePanel.tsx','AssetSignals.tsx'):
    require('frontend/app/fleet-vor-hub/operations/'+file,['export default function'])
print('PASS: PR-04/05 operational controls, configurable checklists, asset icons, queue, active v2 checks present')
