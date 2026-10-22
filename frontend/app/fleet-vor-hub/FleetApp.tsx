// PR06_RECONCILIATION
"use client";

import {useEffect,useState} from "react";
import VorHub from "./VorHub";
import VehicleRegisterPanel from "./register/Panel";
import NewDefectPanel from "./new-defect/Panel";
import ProcessPanel from "./process/Panel";
import WorkflowSettingsPanel from "./operations/WorkflowSettingsPanel";
import OperationsQueuePanel from "./operations/OperationsQueuePanel";
import ReconciliationPanel from "./reconciliation/Panel";
import styles from "./fleet-app.module.css";

type Section="workspace"|"dashboard"|"calendar"|"new-defect"|"register"|"add"|"import"|"status-history"|"process"|"workflow-settings"|"operations-queue"|"reconciliation";
type IconKind="workspace"|"dashboard"|"calendar"|"defect"|"register"|"add"|"import"|"process"|"history"|"settings";
const groups: {label:string;items:{id:Section;label:string;icon:IconKind}[]}[]=[
  {label:"OPERATIONS",items:[
    {id:"workspace",label:"Issue Hub",icon:"workspace"},
    {id:"dashboard",label:"Dashboard",icon:"dashboard"},
    {id:"calendar",label:"Calendar",icon:"calendar"},
    {id:"new-defect",label:"New Defect",icon:"defect"},
    {id:"process",label:"Process Design",icon:"process"},
    {id:"reconciliation",label:"Reconciliation",icon:"history"},
    {id:"workflow-settings",label:"Workflow Settings",icon:"settings"},
    {id:"operations-queue",label:"Actions & Blockers",icon:"history"},
  ]},

];
const labels:Record<Section,string>={
  workspace:"Issue Hub",dashboard:"Dashboard",calendar:"Calendar",
  "new-defect":"New Defect",process:"Process Design",reconciliation:"Reconciliation","workflow-settings":"Workflow Settings","operations-queue":"Actions & Blockers",register:"Vehicle Register",
  add:"Add Vehicle",import:"Import Vehicles","status-history":"Recorded Status History",
};

function NavIcon({name}:{name:IconKind}){
  const common={fill:"none",stroke:"currentColor",strokeWidth:1.75,strokeLinecap:"round" as const,strokeLinejoin:"round" as const};
  return <svg width="19" height="19" viewBox="0 0 24 24" aria-hidden="true" {...common}>
    {name==="workspace"&&<><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M10 10v10"/></>}
    {name==="dashboard"&&<><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="11" width="7" height="10" rx="1"/><rect x="3" y="14" width="8" height="7" rx="1"/></>}
    {name==="calendar"&&<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/></>}
    {name==="defect"&&<><path d="M12 4v16M4 12h16"/><circle cx="12" cy="12" r="10"/></>}
    {name==="register"&&<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8h10M7 12h10M7 16h7"/></>}
    {name==="add"&&<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M12 9v8M8 13h8"/></>}
    {name==="import"&&<><path d="M12 3v13m-4-4 4 4 4-4M4 19v2h16v-2"/></>}
    {name==="history"&&<><path d="M4 6v5h5"/><path d="M4.7 11a8 8 0 1 1 2.3 6.9M12 7v5l3 2"/></>}
    {name==="settings"&&<><circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2m0-14-2 2M7 17l-2 2"/></>}
    {name==="process"&&<><rect x="2" y="4" width="7" height="6" rx="1"/><rect x="15" y="4" width="7" height="6" rx="1"/><rect x="9" y="15" width="7" height="6" rx="1"/><path d="M9 7h6M12 7v8"/></>}
  </svg>;
}

export default function FleetApp(){
  const [section,setSection]=useState<Section>("workspace");
  const [collapsed,setCollapsed]=useState(false);
  const [registerExpanded,setRegisterExpanded]=useState(true);
  const [authenticated,setAuthenticated]=useState<boolean|null>(null);
  const [authError,setAuthError]=useState("");
  const [focusedVehicle,setFocusedVehicle]=useState<string|null>(null);
  useEffect(()=>{
    let active=true;
    fetch("/api/vor/session",{credentials:"same-origin",cache:"no-store"})
      .then(async r=>{if(!r.ok)throw new Error(`Session request failed: ${r.status}`);return await r.json() as {authenticated:boolean}})
      .then(s=>{if(active)setAuthenticated(s.authenticated)})
      .catch(e=>{if(active){setAuthError((e as Error).message);setAuthenticated(false)}});
    return()=>{active=false};
  },[]);
  const navigate=(next:Section)=>{setSection(next);if(["register","add","import","status-history"].includes(next))setRegisterExpanded(true)};
  const logout=async()=>{
    try{await fetch("/api/vor/logout",{method:"POST",body:"{}",headers:{"Content-Type":"application/json"},credentials:"same-origin"})}
    finally{setAuthenticated(false);setSection("workspace");setFocusedVehicle(null)}
  };
  if(authenticated===null)return <div className={styles.loading}>Connecting to Fleet VOR Hub…</div>;
  if(!authenticated)return <div className={styles.fullScreenLogin}>{authError&&<div className={styles.error}>{authError}</div>}<VorHub onAuthChange={setAuthenticated}/></div>;
  const isWorkspace=["workspace","dashboard","calendar"].includes(section);
  return <div className={styles.app}>
    <header className={styles.topbar}>
      <div className={styles.brand}><span className={styles.brandIcon}>F</span><div><strong>Fleet VOR Hub</strong><small>Fleet Operations · synthetic demonstration</small></div></div>
      <div className={styles.topbarActions}>
        <span className={styles.demoFlag}>DEMO v2</span>
        <a href="/api/vor/export.xlsx" download="fleet-vor-demo.xlsx" className={styles.exportButton}>↓ Export Excel</a>
        <button type="button" className={styles.signOut} onClick={()=>void logout()}>Sign out</button>
      </div>
    </header>
    <div className={styles.body}>
      <aside className={`${styles.sidebar} ${collapsed?styles.collapsed:""}`} aria-label="Fleet VOR Hub navigation">
        <button className={styles.collapse} type="button" onClick={()=>setCollapsed(v=>!v)} aria-label={collapsed?"Expand navigation":"Collapse navigation"} title={collapsed?"Expand":"Collapse"}><span>{collapsed?"›":"‹"}</span>{!collapsed&&" Collapse menu"}</button>
        {groups.map(group=><div key={group.label} className={styles.group}>
          {!collapsed&&<div className={styles.groupLabel}>{group.label}</div>}
          {group.items.map(item=><button key={item.id} type="button" className={`${styles.navItem} ${section===item.id?styles.selected:""}`} aria-current={section===item.id?"page":undefined} onClick={()=>navigate(item.id)} title={item.label}>
            <NavIcon name={item.icon}/>{!collapsed&&<span>{item.label}</span>}
          </button>)}
        </div>)}
        <div className={styles.group}>
          {!collapsed&&<div className={styles.groupLabel}>FLEET DATA</div>}
          <div className={styles.registerRow}>
            <button type="button" className={`${styles.navItem} ${["register","add","import","status-history"].includes(section)?styles.selected:""}`} aria-current={section==="register"?"page":undefined} onClick={()=>navigate("register")} title="Vehicle Register">
              <NavIcon name="register"/>{!collapsed&&<span>Vehicle Register</span>}
            </button>
            {!collapsed&&<button type="button" className={styles.navExpand} title={registerExpanded?"Collapse Vehicle Register":"Expand Vehicle Register"} aria-expanded={registerExpanded} aria-label="Toggle Vehicle Register submenu" onClick={()=>setRegisterExpanded(x=>!x)}>{registerExpanded?"▾":"▸"}</button>}
          </div>
          {!collapsed&&registerExpanded&&<div className={styles.subnav} aria-label="Vehicle Register submenu">
            {([['status-history','Recorded Status History','history'],['add','Add Vehicle','add'],['import','Import Vehicles','import']] as const).map(([id,label,icon])=><button key={id} type="button" className={`${styles.subnavItem} ${section===id?styles.subSelected:""}`} onClick={()=>navigate(id)} aria-current={section===id?"page":undefined}>
              <NavIcon name={icon}/><span>{label}</span>
            </button>)}
          </div>}
        </div>
        {!collapsed&&<div className={styles.sidebarFooter}><span className={styles.onlineDot}/>Local demonstration · synthetic data</div>}
      </aside>
      <main className={styles.main} id="fleet-main">
        <div className={styles.contentBar}>
          <div><span className={styles.breadcrumb}>Fleet Operations / {labels[section]}</span><h1>{labels[section]}</h1></div>
          {section!=="new-defect"&&<button type="button" className={styles.primaryAction} onClick={()=>navigate("new-defect")}>+ New Defect</button>}
        </div>
        <div className={`${styles.content} ${isWorkspace?styles.workspaceContent:""}`} key={section}>
          {isWorkspace&&<VorHub embedded externalView={section==="dashboard"||section==="calendar"?section:"vehicles"} initialVehicle={focusedVehicle} onAuthChange={setAuthenticated}/>}
          {(section==="register"||section==="add"||section==="import"||section==="status-history")&&<VehicleRegisterPanel section={section} navigate={navigate}/>}
          {section==="new-defect"&&<NewDefectPanel navigate={next=>navigate(next)} onRegistered={registration=>setFocusedVehicle(registration)}/>}
          {section==="process"&&<ProcessPanel/>}
          {section==="reconciliation"&&<ReconciliationPanel/>}
          {section==="workflow-settings"&&<WorkflowSettingsPanel/>}
          {section==="operations-queue"&&<OperationsQueuePanel onOpenVehicle={registration=>{setFocusedVehicle(registration);navigate("workspace")}}/>}
        </div>
      </main>
    </div>
  </div>;
}
