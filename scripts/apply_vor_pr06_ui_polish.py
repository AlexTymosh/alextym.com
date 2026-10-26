"""PR-06 UI polish: compact workflow, full-height calendar and tidy settings.

Run from anywhere: python scripts/apply_vor_pr06_ui_polish.py
Targets v2 only. Idempotent. Fails when expected integration anchors are missing.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend/app/fleet-vor-hub/VorHub.tsx"
CSS = ROOT / "frontend/app/fleet-vor-hub/vor.module.css"
SETTINGS = ROOT / "frontend/app/fleet-vor-hub/operations/WorkflowSettingsPanel.tsx"
NEW_CSS = ROOT / "frontend/app/fleet-vor-hub/operations/workflow-settings.module.css"
NOTES = ROOT / "Session_Notes.md"
MARK = "/* PR06 UI POLISH: full-height calendar + compact stage cards */"

STAGES = '''       {workflowExpanded&&<ol className={styles.workflowStages} aria-label="Repair workflow stages">{currentSteps.map(s=>{
        const completed = s.status==="done";
        const skipped = s.status==="skipped";
        const active = s.status==="current";
        const opened = expandedStage===s.step_index || (expandedStage===null && active);
        const canComplete = active && !busy && !savingChecklist && checklistReady(s.step_index) && Boolean(selected) && primary?.status==="open";
        const items = stageList(s.step_index);
        const doneItems = items.filter(item=>checklist[`${s.step_index}:${item.key}`]?.checked).length;
        return <li key={`${primary?.id}-${s.step_index}`} className={completed||skipped?styles.stageDone:active?styles.stageCurrent:styles.stagePending}>
          <button type="button" className={styles.stageButton} aria-expanded={opened} aria-label={`${s.label}, ${completed?"completed":skipped?"not required":active?"in progress":"pending"}; ${opened?"collapse":"expand"} checklist`}
             onClick={()=>setExpandedStage(opened?-1:s.step_index)}>
            <span className={styles.stageMarker}>{completed?"✓":skipped?"N/R":s.step_index+1}</span>
            <span className={styles.stageLabel}>{s.label}</span>
            {completed&&<span className={styles.stageStateDone}>✓ Done</span>}
            {skipped&&<span className={styles.stageStateDone}>Not required</span>}
            {active&&<span className={styles.stageStateActive}>{doneItems}/{items.length} checks</span>}
            <span className={styles.stageChevron} aria-hidden="true">{opened?"⌃":"⌄"}</span>
          </button>
          {opened && <div className={styles.stageChecklist} aria-label={`Checklist for ${s.label}`}>
            {completed && doneItems===0 ? <p className={styles.historicStep}>Completed before checklist tracking was recorded.</p> : <>
              {items.length===0 && <p className={styles.historicStep}>No checklist configured for this stage.</p>}
              {items.map(item=><label className={styles.checklistEntry} key={item.key}>
                {item.type==="date" ? <>
                  <span>{item.label}{item.required===false?" (optional)":""}</span>
                  <input type="date" disabled={savingChecklist||busy||!active} value={checklist[`${s.step_index}:${item.key}`]?.value||""}
                    onChange={e=>void saveChecklist(s.step_index,item.key,Boolean(e.target.value),e.target.value||null)}/>
                </> : <>
                  <input type="checkbox" disabled={savingChecklist||busy||!active} checked={checklist[`${s.step_index}:${item.key}`]?.checked||false}
                    onChange={e=>void saveChecklist(s.step_index,item.key,e.target.checked)}/>
                  <span>{item.label}{item.required===false?" (optional)":""}</span>
                </>}
              </label>)}
            </>}
            {active && <div className={styles.stageFooter}>
              {!checklistReady(s.step_index)&&<span>Complete all mandatory checks to continue.</span>}
              <button type="button" className={styles.stageFinish} disabled={!canComplete}
                 onClick={()=>{if(canComplete&&selected&&primary)mutate("/checklists/advance",{vehicle_id:selected.id,ticket_id:primary.id})}}>
                 ✓ Finish stage
              </button>
            </div>}
          </div>}
        </li>;
       })}</ol>}
'''

CSS_EXTRA = r'''
/* PR06 UI POLISH: full-height calendar + compact stage cards */
/* Stretch each week's cells to the remaining calendar height (weeks are set in JSX). */
.root .calendarLayout{height:100%!important;max-height:100%!important;min-height:0!important;align-items:stretch!important}
.root .calendarLayout > .panel:first-child{display:flex!important;flex-direction:column!important;height:100%!important;min-height:0!important;overflow:hidden!important}
.root .calendarLayout .calendarTop,.root .calendarLayout .calendarFilters{flex:0 0 auto!important}
.root .calendarLayout .calendarGrid{flex:1 1 auto!important;min-height:0!important;overflow-y:auto!important;overflow-x:hidden!important;align-content:stretch!important}
.root .calendarLayout .weekday{align-self:stretch}
.root .calendarLayout .dayCell{min-height:110px!important;height:auto!important}
.root .calendarLayout .calendarFootnote{flex:0 0 auto!important}

/* The old template was a horizontal flex list with height:100% buttons.
   Force the stage header and its checklist to flow VERTICALLY. */
.root .workspace .contentPane > .middlePane .workflowStages{display:flex!important;flex-direction:column!important;gap:6px!important;margin:9px 0!important;align-content:start!important;min-height:0!important;padding:0!important}
.root .workspace .contentPane > .middlePane .workflowStages > li{display:flex!important;flex-direction:column!important;align-items:stretch!important;justify-content:flex-start!important;flex:0 0 auto!important;width:100%!important;height:auto!important;min-height:0!important;margin:0!important;padding:3px!important;border-radius:9px!important;gap:0!important}
.root .workspace .contentPane > .middlePane .workflowStages > li > .stageButton{display:flex!important;align-items:center!important;gap:7px!important;height:auto!important;min-height:32px!important;padding:6px 7px!important;flex:0 0 auto!important;line-height:1.25!important;border-radius:7px!important}
.root .workspace .contentPane > .middlePane .workflowStages > li > .stageChecklist{display:grid!important;grid-template-columns:minmax(0,1fr)!important;width:100%!important;min-width:0!important;gap:6px!important;flex:0 0 auto!important;margin:3px 0 0!important;padding:9px 9px 8px!important;border-top:1px solid #e1ebe1!important;background:#fff!important;border-radius:0 0 7px 7px!important}
.root .workspace .contentPane .stageMarker{display:grid!important;place-items:center!important;flex:0 0 22px!important;min-width:22px!important;width:22px!important;height:22px!important;font-size:10px!important}
.root .workspace .contentPane .stageLabel{font-size:11px!important;line-height:1.25!important;flex:1!important;min-width:0!important}
.root .workspace .contentPane .stageChecklist .checklistEntry{display:flex!important;align-items:center!important;gap:8px!important;font-size:11px!important;line-height:1.35!important;min-width:0!important;cursor:pointer}
.root .workspace .contentPane .stageChecklist .checklistEntry input[type=checkbox]{appearance:auto!important;display:inline-block!important;opacity:1!important;visibility:visible!important;flex:0 0 16px!important;width:16px!important;height:16px!important;min-width:16px!important;margin:0!important;accent-color:#64ae72!important}
.root .workspace .contentPane .stageChecklist .checklistEntry input[type=date]{width:100%!important;min-width:0!important;padding:6px!important}
.root .workspace .contentPane .stageChecklist .checklistEntry:has(input[type=date]){display:grid!important;grid-template-columns:1fr!important;gap:3px!important}
.root .workspace .contentPane .workflowStages .stageStateDone{margin-left:auto;white-space:nowrap;font-size:10px;font-weight:800;color:#4a8759}
.root .workspace .contentPane .workflowStages .stageStateActive{margin-left:auto;white-space:nowrap;font-size:10px;font-weight:750;color:#9c773d}
.root .workspace .contentPane .workflowStages .stageChevron{font-size:16px;line-height:1;color:#829989;margin-left:4px}
.root .workspace .contentPane .workflowStages .historicStep{margin:0;font-size:10px;color:#7d8e80}
.root .workspace .contentPane .workflowStages .stageFooter{display:flex;align-items:center;justify-content:space-between;gap:7px;padding-top:8px;border-top:1px solid #edf2ed;color:#85683d;font-size:10px}
.root .workspace .contentPane .workflowStages .stageFinish{flex-shrink:0;padding:7px 10px;border:0;border-radius:7px;background:#4f865e;color:white;font-size:10px;font-weight:750;cursor:pointer}
.root .workspace .contentPane .workflowStages .stageFinish:disabled{opacity:.45;cursor:default}
@media(max-width:900px){.root .calendarLayout{height:auto!important;max-height:none!important;min-height:650px!important}.root .calendarLayout > .panel:first-child{min-height:650px!important}.root .calendarLayout .calendarGrid{min-height:470px!important}}
'''


def replace_exact(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def apply() -> None:
    for p in (FRONT, CSS, SETTINGS, NEW_CSS):
        if not p.is_file():
            raise RuntimeError(f"Missing file: {p.relative_to(ROOT)}. Unzip the patch first.")
    frozen = ROOT / "frontend/app/fleet-vor-hub-01"
    if not frozen.is_dir():
        raise RuntimeError("Frozen v1 directory not found; aborting.")
    src = FRONT.read_text(encoding="utf-8")
    current_css = CSS.read_text(encoding="utf-8")
    # A grid sized to the number of displayed weeks fills the calendar card.
    src = replace_exact(src, 'className={styles.calendarGrid}>{["Mon",',
                        'className={styles.calendarGrid} style={{gridTemplateRows:`32px repeat(${Math.ceil(cells.length/7)}, minmax(110px, 1fr))`}}>{["Mon",',
                        "calendar grid rows")
    if 'const [expandedStage,setExpandedStage]' not in src:
        src = replace_exact(src,
                            ' const [workflowExpanded,setWorkflowExpanded]=useState(true);',
                            ' const [workflowExpanded,setWorkflowExpanded]=useState(true);\n const [expandedStage,setExpandedStage]=useState<number|null>(null);',
                            "stage expanded state")
    new_mark = '       {workflowExpanded&&<ol className={styles.workflowStages} aria-label="Repair workflow stages">'
    if new_mark not in src:
        old_mark = '       {workflowExpanded&&<ol className={styles.workflowStages}>{currentSteps.map(s=>{'
        end_mark = '       {currentSteps.length===0&&<p className={styles.workflowEmpty}>'
        if src.count(old_mark) != 1 or src.count(end_mark) != 1:
            raise RuntimeError("Repair workflow JSX anchors missing or ambiguous; no files written")
        start = src.index(old_mark)
        end = src.index(end_mark, start)
        src = src[:start] + STAGES + src[end:]
    if MARK not in current_css:
        current_css += "\n" + CSS_EXTRA
    # Commit only after ALL transformations validate.
    if src != FRONT.read_text(encoding="utf-8"):
        FRONT.write_text(src, encoding="utf-8", newline="\n")
        print("Updated:", FRONT.relative_to(ROOT))
    else:
        print("Already patched:", FRONT.relative_to(ROOT))
    if current_css != CSS.read_text(encoding="utf-8"):
        CSS.write_text(current_css, encoding="utf-8", newline="\n")
        print("Updated:", CSS.relative_to(ROOT))
    else:
        print("Already patched:", CSS.relative_to(ROOT))
    heading = "### PR-06 UI polish — Workflow, Calendar, Settings (22 October 2026)"
    if NOTES.is_file() and heading not in NOTES.read_text(encoding="utf-8"):
        with NOTES.open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n" + heading + "\n\n- Workflow Settings: compact two-column expandable stage editor; save/discard per stage; previous audit is preserved.\n- Calendar: week rows stretch vertically to occupy the booking calendar panel. Filters remain unchanged.\n- Fleet Workspace: compact stage cards with visible completion ticks, optional checklist expansion, checkboxes shown vertically and only the current stage editable. Historical stages without recorded checklist evidence are not falsely ticked.\n- Frozen v1, backend APIs and databases unchanged. Local typecheck/build and browser tests required.\n")
    print("UI polish integrated. Frozen v1 and backend unchanged.")


if __name__ == "__main__":
    apply()
