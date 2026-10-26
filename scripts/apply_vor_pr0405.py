"""Integrate Fleet VOR Hub PR-04+05 into the existing local project.

Run from any directory: python scripts/apply_vor_pr0405.py
Fails before writing if expected PR-03 integration anchors are absent. Re-running is safe.
Only updates active Fleet VOR Hub v2 files.
"""
from __future__ import annotations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FRONT=ROOT/'frontend/app/fleet-vor-hub/VorHub.tsx'
SHELL=ROOT/'frontend/app/fleet-vor-hub/FleetApp.tsx'
MAIN=ROOT/'backend/app/main.py'
CHECK=ROOT/'backend/app/api/vor_checklist.py'
DATA=ROOT/'backend/app/services/vor_data.py'
API_VOR=ROOT/'backend/app/api/vor.py'
STORE=ROOT/'backend/app/services/vor_store.py'
NOTES=ROOT/'Session_Notes.md'
TAG='// PR0405: case-based operational control and asset signals'

def update_once(source: str, old: str, new: str, name: str) -> str:
    if new in source:
        return source
    count=source.count(old)
    if count!=1:
        raise RuntimeError(f'{name}: expected one anchor, found {count}: {old[:120]}')
    return source.replace(old,new,1)

def apply():
    prerequisite=[FRONT,SHELL,MAIN,CHECK,DATA,API_VOR,STORE,
        ROOT/'backend/app/api/vor_operations.py',ROOT/'backend/app/services/vor_operations.py',
        ROOT/'frontend/app/fleet-vor-hub/operations/OperationsPanel.tsx',
        ROOT/'frontend/app/fleet-vor-hub/operations/WorkflowSettingsPanel.tsx',
        ROOT/'frontend/app/fleet-vor-hub/operations/OperationsQueuePanel.tsx',
        ]
    for path in prerequisite:
        if not path.is_file():raise RuntimeError(f'Missing file: {path.relative_to(ROOT)}')
    front=FRONT.read_text(encoding='utf-8')
    shell=SHELL.read_text(encoding='utf-8')
    main=MAIN.read_text(encoding='utf-8')
    check=CHECK.read_text(encoding='utf-8')
    data=DATA.read_text(encoding='utf-8')
    api_vor=API_VOR.read_text(encoding='utf-8')
    store=STORE.read_text(encoding='utf-8')

    if TAG not in front:
        front=update_once(front,'import styles from "./vor.module.css";','import styles from "./vor.module.css";\nimport OperationsPanel from "./operations/OperationsPanel";\nimport AssetSignals,{type OpsIndicator} from "./operations/AssetSignals";','VorHub imports')
        front=update_once(front,' const [session,setSession]=useState',
            ' '+TAG+'\n const [opsOverview,setOpsOverview]=useState<Record<string,OpsIndicator>>({});\n const [session,setSession]=useState','VorHub state')
        orig='const payload=await request<Data>("/bootstrap");setData(payload);setClock(c=>c+1)'
        changed='const payload=await request<Data>("/bootstrap");setData(payload);request<{vehicles:Record<string,OpsIndicator>}>("/ops/overview").then(r=>setOpsOverview(r.vehicles)).catch(()=>setOpsOverview({}));setClock(c=>c+1)'
        front=update_once(front,orig,changed,'VorHub overview loader')
        card='<div className={styles.vehicleWorkshop}><span>Workshop</span><strong>{v.garage}</strong></div></button>)'
        front=update_once(front,card,'<div className={styles.vehicleWorkshop}><span>Workshop</span><strong>{v.garage}</strong></div><AssetSignals value={opsOverview[String(v.id)]}/></button>)','Vehicle card indicators')
        tip='{currentSteps.length===0&&<p className={styles.workflowEmpty}>No stages assigned to this ticket.</p>}'
        front=update_once(front,tip,tip+'\n       {selected&&<OperationsPanel key={`${selected.id}-${primary?.id||"no-ticket"}`} vehicleId={selected.id} ticketId={primary?.id||null} onSaved={load}/>}','Right workflow operational panel')
        # Template validation now reflects configurable required item flags.
        state=' const [savingChecklist,setSavingChecklist]=useState(false);'
        template_hook='''
 const [configuredStages,setConfiguredStages]=useState<Record<number,{key:string;label:string;required?:boolean;type?:"date"}[]>>({});
 useEffect(()=>{if(!session?.authenticated)return;
   request<{items:{stage_index:number;item_key:string;label:string;required:boolean}[]}>('/ops/templates')
      .then(r=>{const byStage:Record<number,{key:string;label:string;required?:boolean;type?:"date"}[]>={};
        for(const item of r.items){(byStage[item.stage_index]??=[]).push({key:item.item_key,label:item.label,required:item.required,type:item.item_key==="diagnosis_date"?"date":undefined});}
        setConfiguredStages(byStage);}).catch(()=>{});
 },[session?.authenticated]);
 const stageList=(i:number):{key:string;label:string;required?:boolean;type?:"date"}[]=>configuredStages[i]||WORKFLOW_ITEMS[i]||[];
'''
        front=update_once(front,state,state+template_hook,'Configurable step items state')
        front=update_once(front,'const checklistReady=(index:number)=>(WORKFLOW_ITEMS[index]||[]).every(',
            'const checklistReady=(index:number)=>stageList(index).filter(item=>item.required!==false).every(','Required item gate')
        front=update_once(front,'(WORKFLOW_ITEMS[s.step_index]||[]).map(item=>', 'stageList(s.step_index).map(item=>','Checklist item labels')
        front=front.replace('{item.label}</span></>:', '{item.label}{item.required===false?" (optional)":""}</span></>:')
        front=front.replace('<span>{item.label}</span></>}', '<span>{item.label}{item.required===false?" (optional)":""}</span></>}')
        # Indicate historic Not required stages appropriately.
        front=front.replace('currentSteps.filter(s=>s.status==="done").length', 'currentSteps.filter(s=>s.status==="done"||s.status==="skipped").length')
        front=front.replace('s.status==="done"?styles.progressDone:', '(s.status==="done"||s.status==="skipped")?styles.progressDone:')
        front=front.replace('s.status==="done"?styles.stageDone:', '(s.status==="done"||s.status==="skipped")?styles.stageDone:')
        front=front.replace('s.status==="done"?"✓":s.step_index+1', 's.status==="done"?"✓":s.status==="skipped"?"N/R":s.step_index+1')
    if 'WorkflowSettingsPanel' not in shell:
        shell=update_once(shell,'import ProcessPanel from "./process/Panel";','import ProcessPanel from "./process/Panel";\nimport WorkflowSettingsPanel from "./operations/WorkflowSettingsPanel";\nimport OperationsQueuePanel from "./operations/OperationsQueuePanel";','Shell settings import')
        shell=update_once(shell,'"status-history"|"process";', '"status-history"|"process"|"workflow-settings"|"operations-queue";', 'Section union')
        shell=update_once(shell,'|"process"|"history";', '|"process"|"history"|"settings";', 'Icon union')
        shell=update_once(shell,'{id:"process",label:"Process Design",icon:"process"},','{id:"process",label:"Process Design",icon:"process"},\n    {id:"workflow-settings",label:"Workflow Settings",icon:"settings"},\n    {id:"operations-queue",label:"Actions & Blockers",icon:"history"},','Settings menu')
        shell=update_once(shell,'"new-defect":"New Defect",process:"Process Design",register:"Vehicle Register",','"new-defect":"New Defect",process:"Process Design","workflow-settings":"Workflow Settings","operations-queue":"Actions & Blockers",register:"Vehicle Register",','Settings heading')
        shell=update_once(shell,'{name==="process"&&', '{name==="settings"&&<><circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2m0-14-2 2M7 17l-2 2"/></>}\n    {name==="process"&&','Settings icon')
        shell=update_once(shell,'{section==="process"&&<ProcessPanel/>}', '{section==="process"&&<ProcessPanel/>}\n          {section==="workflow-settings"&&<WorkflowSettingsPanel/>}\n          {section==="operations-queue"&&<OperationsQueuePanel onOpenVehicle={registration=>{setFocusedVehicle(registration);navigate("workspace")}}/>}','Settings view')
    if 'vor_operations_router' not in main:
        main=update_once(main,'from app.api.vor import router as vor_router','from app.api.vor import router as vor_router\nfrom app.api.vor_operations import router as vor_operations_router','Backend import')
        main=update_once(main,'    app.include_router(vor_router, prefix="/api")', '    app.include_router(vor_router, prefix="/api")\n    app.include_router(vor_operations_router, prefix="/api")','Backend router')
    if 'ops.required_keys(db,index)' not in check:
        check=update_once(check,'from app.services import vor_store','from app.services import vor_store, vor_operations as ops','Checklist imports')
        check=update_once(check,'pending=set(CHECKLIST[index])-completed','pending=ops.required_keys(db,index)-completed','Checklist required items')
    # PR-02 legacy status endpoint: seed SQLite uses Operational, never Available.
    data=data.replace('status not in {"VOR","Available"}', 'status not in {"VOR","Operational"}')
    data=data.replace("CASE WHEN ?='Available'", "CASE WHEN ?='Operational'")
    # Route the older v2 /advance endpoint through the same checklist gate.
    # Frozen v1 is mounted by its own router and is not altered.
    if 'advance_with_checks(AdvanceStage(' not in api_vor:
        old='    try:\n        vor_store.advance_workflow(body.vehicle_id, body.ticket_id)\n    except ValueError as exc:\n        raise HTTPException(422, str(exc)) from exc\n    return {"ok": True}'
        new='    from app.api.vor_checklist import AdvanceStage, advance_with_checks\n    return advance_with_checks(AdvanceStage(vehicle_id=body.vehicle_id, ticket_id=body.ticket_id), request)'
        api_vor=update_once(api_vor,old,new,'Legacy v2 advance endpoint')
    # Changing a scenario restarts its checklist and release-stage evidence.
    reset_marker='        db.execute("DELETE FROM ticket_steps WHERE ticket_id=?", (ticket_id,))'
    reset_extra='        for table_name in ("vor_step_checklists", "ops_stage_skips", "ops_release_checks"):\n            if db.execute("SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?", (table_name,)).fetchone():\n                db.execute(f"DELETE FROM {table_name} WHERE ticket_id=?", (ticket_id,))\n'
    if 'for table_name in ("vor_step_checklists"' not in store:
        store=update_once(store,reset_marker,reset_extra+reset_marker,'Reset stale checklist evidence on scenario change')
    # Don't change past v1 or database snapshots.
    for path,new in [(FRONT,front),(SHELL,shell),(MAIN,main),(CHECK,check),(DATA,data),(API_VOR,api_vor),(STORE,store)]:
        if path.read_text(encoding='utf-8')!=new:
            path.write_text(new,encoding='utf-8',newline='\n');print('Updated:',path.relative_to(ROOT))
        else:print('Already patched:',path.relative_to(ROOT))
    if NOTES.is_file():
        heading='### PR-04 + PR-05 combined — Operational Control and asset indicators (2026-10-21)'
        notes=NOTES.read_text(encoding='utf-8')
        if heading not in notes:
            with NOTES.open('a',encoding='utf-8',newline='\n') as f:
                f.write('\n'+heading+'\n\n- v2-only tasks/deadlines, blockers, documents, release checks, manual VOR/Operational status confirmation and operational audit.\n- Workflow Settings exposes editable item labels and required flags (date remains required); current stage can be marked Not required with recorded actor/reason.\n- Right-side workflow displays operational controls; vehicle cards show live task, overdue, blockers, documents, release and progress indicators.\n- No external system updates and no automatic release. Frozen v1 source/database untouched.\n- User must run local backend tests, frontend typecheck/build and browser smoke tests before commit.\n')
    print('PR-04+05 integration complete. Frozen v1 was not modified.')

if __name__=='__main__': apply()
