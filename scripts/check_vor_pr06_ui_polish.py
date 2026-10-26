"""Static smoke checks for the v2-only UI refinement."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ui=(ROOT/'frontend/app/fleet-vor-hub/VorHub.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/app/fleet-vor-hub/vor.module.css').read_text(encoding='utf-8')
settings=(ROOT/'frontend/app/fleet-vor-hub/operations/WorkflowSettingsPanel.tsx').read_text(encoding='utf-8')
settings_css=(ROOT/'frontend/app/fleet-vor-hub/operations/workflow-settings.module.css').read_text(encoding='utf-8')
assert 'gridTemplateRows:`32px repeat(${Math.ceil(cells.length/7)}' in ui
assert 'const [expandedStage,setExpandedStage]' in ui
assert 'className={styles.stageStateDone}>✓ Done' in ui
assert 'className={styles.stageChecklist}' in ui
assert 'disabled={savingChecklist||busy||!active}' in ui
assert 'height:auto!important' in css
assert 'workflowStages > li{display:flex!important;flex-direction:column' in css
assert 'workflow-settings.module.css' in settings
assert 'Save stage' in settings and 'Discard' in settings
assert '.stageList{display:grid' in settings_css
assert (ROOT/'frontend/app/fleet-vor-hub-01').is_dir()
print('PASS: compact workflow stages, visible checklist ticks, full-height calendar, redesigned settings; frozen v1 preserved')
