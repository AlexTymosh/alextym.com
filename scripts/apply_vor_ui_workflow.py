"""Apply v2-only calendar, workflow and checklist integrations.

Run from any directory with: python scripts/apply_vor_ui_workflow.py
Idempotent and fail-fast: validates all anchors before writing any file.
"""
from __future__ import annotations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FRONT=ROOT/'frontend/app/fleet-vor-hub/VorHub.tsx'
CSS=ROOT/'frontend/app/fleet-vor-hub/vor.module.css'
MAIN=ROOT/'backend/app/main.py'
NOTES=ROOT/'Session_Notes.md'
EXPORTS=ROOT/'backend/app/services/vor_exports.py'
MARK='/* v2 UX refinement: calendar filters + right-side checklist */'

ITEMS='''
// The checklist is stored in v2 SQLite; its keys are validated by the backend.
const WORKFLOW_ITEMS: Record<number,{key:string;label:string;type?:"date"}[]> = {
  0:[{key:"notification_sent",label:"Details sent to service company"},{key:"response_received",label:"Acknowledgement received"}],
  1:[{key:"information_forwarded",label:"Defect information passed on"},{key:"visit_date_agreed",label:"Inspection date agreed"},{key:"diagnosis_date",label:"Agreed date",type:"date"},{key:"maintenance_combination_reviewed",label:"Combining with MOT / inspection / service checked"}],
  2:[{key:"inspected",label:"Specialist inspection completed"},{key:"initial_quote_received",label:"Initial quotation received"},{key:"preliminary_estimate_confirmed",label:"Preliminary estimate confirmed"}],
  3:[{key:"approval_recorded",label:"Repair authorised"}],
  4:[{key:"work_started",label:"Work started"},{key:"repair_finished",label:"Work completed"}],
  5:[{key:"repair_verified",label:"Repair completion confirmed"},{key:"release_checked",label:"Release and safety checks completed"}],
  6:[{key:"hoth_informed",label:"Operations desk notified"},{key:"hoth_closed_confirmed",label:"Ticket closure confirmed"}],
  7:[{key:"documents_received",label:"Post-repair documents received"},{key:"documents_checked",label:"Documents reviewed"}],
};
type ChecklistItem = {step_index:number;key:string;checked:boolean;value:string|null};
'''

STATE='''
 const [checklist,setChecklist]=useState<Record<string,{checked:boolean;value:string|null}>>({});
 const [savingChecklist,setSavingChecklist]=useState(false);
 useEffect(()=>{let active=true;
   if(!primary?.id){setChecklist({});return;}
   request<{items:ChecklistItem[]}>(`/checklists/${encodeURIComponent(primary.id)}`)
     .then(r=>{if(active)setChecklist(Object.fromEntries(r.items.map(x=>[`${x.step_index}:${x.key}`,{checked:x.checked,value:x.value}])));})
     .catch(e=>{if(active)setNotice((e as Error).message)});
   return()=>{active=false};
 },[primary?.id,clock]);
 const checklistReady=(index:number)=>(WORKFLOW_ITEMS[index]||[]).every(item=>checklist[`${index}:${item.key}`]?.checked);
 const saveChecklist=async(index:number,key:string,checked:boolean,value:string|null=null)=>{
   if(!selected||!primary)return;
   setSavingChecklist(true);
   try{await request('/checklists',{method:'POST',body:JSON.stringify({vehicle_id:selected.id,ticket_id:primary.id,step_index:index,key,checked,value})});
     setChecklist(prev=>({...prev,[`${index}:${key}`]:{checked,value}}));
   }catch(e){setNotice((e as Error).message)}finally{setSavingChecklist(false)}
 };
'''
CHECKBOX='''
          <div className={styles.stageChecklist} aria-label={`Checklist for ${s.label}`}>
            {(WORKFLOW_ITEMS[s.step_index]||[]).map(item=><label className={styles.checklistEntry} key={item.key}>
              {item.type==="date"?<><span>{item.label}</span><input type="date" disabled={savingChecklist||busy||s.status==="done"} value={checklist[`${s.step_index}:${item.key}`]?.value||""} onChange={e=>void saveChecklist(s.step_index,item.key,Boolean(e.target.value),e.target.value||null)}/></>:
                <><input type="checkbox" disabled={savingChecklist||busy||s.status==="done"} checked={checklist[`${s.step_index}:${item.key}`]?.checked||false} onChange={e=>void saveChecklist(s.step_index,item.key,e.target.checked)}/><span>{item.label}</span></>}
            </label>)}
            {s.status==="current"&&!checklistReady(s.step_index)&&<small className={styles.checklistHint}>Complete the checklist to finish this stage.</small>}
            {s.status==="done"&&!checklistReady(s.step_index)&&<small className={styles.checklistHint}>Historical completion: checklist was not recorded.</small>}
          </div>
'''
CALENDAR_FILTERS='''
 const [cityFilter,setCityFilter]=useState("all");
 const [partnerFilter,setPartnerFilter]=useState("all");
 const [typeFilter,setTypeFilter]=useState("all");
 const vehicleBase=(id:number)=>data.vehicles.find(v=>v.id===id)?.garage||"Unassigned";
 const cities=Array.from(new Set(data.bookings.map(b=>vehicleBase(b.vehicle_id)))).sort();
 const partners=Array.from(new Set(data.bookings.map(b=>b.garage))).sort();
'''
CALENDAR_UI='''
   <div className={styles.calendarFilters} aria-label="Calendar booking filters">
    <label>City / vehicle base<select value={cityFilter} onChange={e=>setCityFilter(e.target.value)}><option value="all">All bases</option>{cities.map(c=><option key={c} value={c}>{c}</option>)}</select></label>
    <label>Partner / booked garage<select value={partnerFilter} onChange={e=>setPartnerFilter(e.target.value)}><option value="all">All partners</option>{partners.map(g=><option key={g} value={g}>{g}</option>)}</select></label>
    <label>Booking type<select value={typeFilter} onChange={e=>setTypeFilter(e.target.value)}><option value="all">All types</option>{TYPES.map(t=><option key={t} value={t}>{t}</option>)}</select></label>
    <button type="button" onClick={()=>{setCityFilter("all");setPartnerFilter("all");setTypeFilter("all")}}>Clear filters</button>
   </div>
'''

NEW_CSS='''
/* v2 UX refinement: calendar filters + right-side checklist */
.root .dayCell{min-height:125px!important}
.calendarFilters{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin:0 18px 13px;padding:10px 13px;border:1px solid #d6e2d8;background:#f6faf6;border-radius:9px}
.calendarFilters label{display:grid;gap:4px;min-width:150px;flex:1;font-size:11px;font-weight:700;color:#536b5b}
.calendarFilters select{min-height:35px;font-size:12px;padding:6px 8px}
.calendarFilters button{background:#fff;border:1px solid #cddace;border-radius:8px;padding:8px 12px;font-size:11px;color:#456a4f}
.root .workspace .contentPane{display:grid!important;grid-template-columns:minmax(0,1fr) clamp(285px,25vw,360px)!important;grid-template-rows:auto minmax(0,1fr)!important;gap:9px!important}
.root .workspace .contentPane>.caseColumn{grid-column:1 / -1!important;grid-row:1!important;min-width:0;display:block!important}
.root .workspace .contentPane>.chatterPane{grid-column:1!important;grid-row:2!important;height:100%!important;min-height:0!important;max-height:none!important}
.root .workspace .contentPane>.middlePane{grid-column:2!important;grid-row:2!important;min-height:0!important;max-height:100%!important;display:flex!important;flex-direction:column;background:#fbfdfb;border:1px solid #cbdccc;border-radius:13px;padding:12px;overflow-y:auto;overflow-x:hidden;box-shadow:0 3px 15px #254a3220}
.root .workspace .contentPane>.middlePane .workflow{padding:0!important;overflow:visible}
.root .workspace .contentPane>.middlePane .workflowSummary{display:grid!important;gap:8px}
.root .workspace .contentPane>.middlePane .currentStageButton{max-width:none;min-width:0;width:100%}
.root .workspace .contentPane>.middlePane .workflowStages{display:grid!important;grid-template-columns:1fr!important;gap:9px!important;overflow:visible;max-height:none}
.root .workspace .contentPane>.middlePane .workflowStages>li{padding:7px;border:1px solid #dee9df;background:#fff;border-radius:10px}
.root .workspace .contentPane>.middlePane .stageButton{width:100%;min-height:38px!important;text-align:left}
.stageChecklist{border-top:1px solid #edf0ec;margin:7px 0 0;padding:8px 3px 3px;display:grid;gap:8px}
.checklistEntry{display:flex;align-items:center;gap:7px;font-size:11px;font-weight:500;color:#3a4d41;line-height:1.4}
.checklistEntry input[type=checkbox]{width:16px;height:16px;flex:0 0 16px;accent-color:#64ae72}
.checklistEntry input[type=date]{width:100%;min-width:0;padding:6px!important;font-size:11px}
.checklistEntry:has(input[type=date]){display:grid;grid-template-columns:1fr;gap:3px}
.checklistHint{font-size:10px;color:#8d6a34;margin-top:5px}
@media(max-width:1050px){.root .workspace .contentPane{grid-template-columns:minmax(0,1fr) 275px!important}}
@media(max-width:850px){.root .workspace .contentPane{display:flex!important;flex-direction:column!important;max-height:none!important;overflow:visible!important}.root .workspace .contentPane>.chatterPane{min-height:440px!important;height:440px!important;flex:none!important}.root .workspace .contentPane>.middlePane{max-height:none!important;min-height:360px!important;overflow:visible!important;flex:none!important}.root .dayCell{min-height:90px!important}}
'''

def replace_once(src:str, old:str, new:str, name:str)->str:
    if new in src:
        return src
    if src.count(old)!=1:
        raise RuntimeError(f'{name}: expected one source anchor, found {src.count(old)}: {old[:70]}')
    return src.replace(old,new,1)


def apply()->None:
    required=[ROOT/'frontend/app/fleet-vor-hub/FleetApp.tsx',ROOT/'frontend/app/fleet-vor-hub-01/page.tsx',ROOT/'backend/app/services/vor_store_v1.py',ROOT/'backend/app/api/vor_checklist.py',EXPORTS]
    for path in required:
        if not path.is_file():raise RuntimeError(f'Missing PR prerequisite: {path.relative_to(ROOT)}')
    if not (ROOT/'backend/_local/vor_hub_01.sqlite3').is_file():raise RuntimeError('Frozen v1 database is missing')
    frontend=FRONT.read_text(encoding='utf-8')
    if 'WORKFLOW_ITEMS: Record<number,' not in frontend:
        frontend=replace_once(frontend,'const two = (x:number)',ITEMS+'\nconst two = (x:number)','workflow constants')
    if 'const [cityFilter,setCityFilter]' not in frontend:
        frontend=replace_once(frontend,' const first=new Date(cursor.year,cursor.month,1);',CALENDAR_FILTERS+' const first=new Date(cursor.year,cursor.month,1);','calendar hooks')
    old=' const visibleBookings = data.bookings.filter(b=>b.booked_date.startsWith(isoMonth(cursor.year,cursor.month)));'
    new=' const visibleBookings = data.bookings.filter(b=>b.booked_date.startsWith(isoMonth(cursor.year,cursor.month)) && (cityFilter==="all"||vehicleBase(b.vehicle_id)===cityFilter) && (partnerFilter==="all"||b.garage===partnerFilter) && (typeFilter==="all"||b.kind===typeFilter));'
    frontend=replace_once(frontend,old,new,'calendar filtered bookings')
    if 'className={styles.calendarFilters}' not in frontend:
        frontend=replace_once(frontend,'   <div className={styles.calendarGrid}>',CALENDAR_UI+'   <div className={styles.calendarGrid}>','calendar filters UI')
    if 'useState<Record<string,{checked:boolean;value:string|null}>>' not in frontend:
        frontend=replace_once(frontend,' const doneStages=currentSteps.filter(s=>s.status==="done").length;',STATE+' const doneStages=currentSteps.filter(s=>s.status==="done").length;','workflow checklist hooks')
    frontend=replace_once(frontend,' const canAdvanceStage=Boolean(selected&&primary?.status==="open"&&currentStage&&!busy);',' const canAdvanceStage=Boolean(selected&&primary?.status==="open"&&currentStage&&!busy&&!savingChecklist&&checklistReady(currentStage.step_index));','stage gate')
    # Keep the current ticket workflow stage UI, insert the checklist inside each stage.
    if 'styles.stageChecklist' not in frontend:
        frontend=replace_once(frontend,'         </button>\n        </li>;','         </button>'+CHECKBOX+'        </li>;','workflow stage detail')
    frontend=frontend.replace('const canComplete = s.status==="current" && !busy && Boolean(selected) && primary?.status==="open";', 'const canComplete = s.status==="current" && !busy && !savingChecklist && checklistReady(s.step_index) && Boolean(selected) && primary?.status==="open";')
    frontend=frontend.replace('mutate("/advance",','mutate("/checklists/advance",')
    frontend=frontend.replace('const [workflowExpanded,setWorkflowExpanded]=useState(false);','const [workflowExpanded,setWorkflowExpanded]=useState(true);')
    if 'SECTION_WORKFLOW_MOVED' not in frontend:
        start=frontend.index('    <section className={styles.middlePane}>')
        end_text='    </section>\n      </div>\n    <section className={`${styles.panel} ${styles.chatterPane}`}'
        end=frontend.index(end_text,start)+len('    </section>')
        workflow=frontend[start:end]
        frontend=frontend[:start]+frontend[end:]
        endmarker='    </section>\n      </div>\n  </main>}'
        if frontend.count(endmarker)!=1:
            raise RuntimeError('Cannot find unique chatter bottom; no source files written')
        frontend=frontend.replace(endmarker,'    </section>\n'+workflow+'\n      </div>\n  </main>}',1)
        # JSX comment marks the one-way structural migration for idempotency.
        frontend=frontend.replace('    <section className={styles.middlePane}>','    {/* SECTION_WORKFLOW_MOVED */}\n    <section className={styles.middlePane}>',1)
    # New UI labels, while preserving stored data and kind identifiers used by the API.
    frontend=frontend.replace('label:"KEY2"','label:"Status log"').replace('>KEY2</','>Status log</')
    frontend=frontend.replace('{e.body}</p>','{e.body.replace(/\\b(KEY2|NHS)\\b/gi,"Fleet system")}</p>')
    frontend=frontend.replace('>{e.kind.toUpperCase()}</span>','>{e.kind==="key2"?"STATUS LOG":e.kind.toUpperCase()}</span>')
    frontend=frontend.replace('<b>{e.author}</b>','<b>{e.author.replace(/\\b(KEY2|NHS)\\b/gi,"Fleet system")}</b>')
    frontend=frontend.replace('{e.subject}</strong>','{e.subject.replace(/\\b(KEY2|NHS)\\b/gi,"Fleet system")}</strong>')
    css=CSS.read_text(encoding='utf-8')
    if MARK not in css: css+='\n'+NEW_CSS
    main=MAIN.read_text(encoding='utf-8')
    if 'vor_checklist_router' not in main:
        main=replace_once(main,'from app.api.vor import router as vor_router','from app.api.vor import router as vor_router\nfrom app.api.vor_checklist import router as vor_checklist_router','main import')
        main=replace_once(main,'    app.include_router(vor_router, prefix="/api")','    app.include_router(vor_router, prefix="/api")\n    app.include_router(vor_checklist_router, prefix="/api")','main router')
    exports=EXPORTS.read_text(encoding='utf-8')
    exports=exports.replace('                "KEY2",', '                "Status register",')
    # All updates validated; now write. Avoid modifying frozen v1.
    for path,new in [(FRONT,frontend),(CSS,css),(MAIN,main),(EXPORTS,exports)]:
        if path.read_text(encoding='utf-8')!=new:
            path.write_text(new,encoding='utf-8',newline='\n');print('Updated:',path.relative_to(ROOT))
        else:print('Already patched:',path.relative_to(ROOT))
    if NOTES.is_file():
        note='### Session 2026-10-21 — UX refinement and workflow checklist'
        content=NOTES.read_text(encoding='utf-8')
        if note not in content:
            with NOTES.open('a',encoding='utf-8',newline='\n') as f:f.write('\n'+note+'\n\n- Removed visible brand/system references from v2 UI only; source data keys unchanged.\n- Calendar: taller cells and type, vehicle-base/city, and booked-garage/partner filters. True booking city/partner fields remain future schema work.\n- Defect reason: radio selection required and initially empty.\n- Process: compact movable swimlane cards; roadmap still places full management dashboard in PR-07.\n- Fleet Workspace: right-side persisted stage checklist; all stage items required before advance via new endpoint.\n- Frozen v1 is untouched.\n')
    print('UI/workflow integration complete; frozen v1 files unchanged')

if __name__=='__main__':apply()
