"use client";
import {useCallback,useEffect,useState,type FormEvent} from "react";
import styles from "./operations.module.css";

const URL="/api/vor/ops";
const RELEASE=[
  ["garage_complete","Garage confirmed repair completed"],
  ["safety_checked","Safety and roadworthiness checks completed"],
  ["equipment_checked","Required vehicle equipment checked"],
  ["fleet_release_approved","Fleet release approval recorded"],
] as const;
const BLOCKERS=["Awaiting response","Parts","Supplier","Approval","Booking","Documents","Other"];
const DOCUMENTS=["Repair report","Invoice","Work completion confirmation","Release certificate","Other"];
type Task={id:number;title:string;owner:string;due_at:string;status:"open"|"done"};
type Blocker={id:number;kind:string;detail:string;status:"active"|"resolved"};
type Doc={id:number;kind:string;reference:string;status:"missing"|"received"|"verified"};
type Release={item_key:string;checked:number};
type Audit={action:string;actor:string;details:string;created_at:string};
type Details={actions:Task[];blockers:Blocker[];documents:Doc[];release:Release[];audit:Audit[];status:{availability_status:string;registration:string};skips:{stage_index:number;actor:string;reason:string;skipped_at:string}[]};
async function api<T>(path:string,body?:object):Promise<T>{
 const r=await fetch(URL+path,{credentials:"same-origin",cache:"no-store",method:body?"POST":"GET",headers:body?{"Content-Type":"application/json"}:undefined,body:body?JSON.stringify(body):undefined});
 const j=await r.json().catch(()=>({detail:`HTTP ${r.status}`}));
 if(!r.ok)throw new Error(typeof j.detail==="string"?j.detail:`HTTP ${r.status}`);
 return j as T;
}
const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;};

export default function OperationsPanel({vehicleId,ticketId,onSaved}:{vehicleId:number;ticketId:string|null;onSaved:()=>Promise<void>}){
 const [data,setData]=useState<Details|null>(null);
 const [error,setError]=useState("");const [notice,setNotice]=useState("");const [busy,setBusy]=useState(false);
 const [section,setSection]=useState<"actions"|"blockers"|"documents"|"release"|"status"|"audit">("actions");
 const [title,setTitle]=useState("");const [owner,setOwner]=useState("");const [due,setDue]=useState(today());
 const [blockerType,setBlockerType]=useState("Awaiting response");const [blockerText,setBlockerText]=useState("");
 const [docType,setDocType]=useState("Repair report");const [docRef,setDocRef]=useState("");const [docStatus,setDocStatus]=useState("missing");
 const [reason,setReason]=useState("");const [confirmed,setConfirmed]=useState(false);const [override,setOverride]=useState(false);
 const [skipReason,setSkipReason]=useState("");const [skipActor,setSkipActor]=useState("Fleet Department");
 const load=useCallback(async()=>{if(!ticketId){setData(null);return;} const query=`?vehicle_id=${vehicleId}&ticket_id=${encodeURIComponent(ticketId)}`;setData(await api<Details>(`/details${query}`));},[vehicleId,ticketId]);
 useEffect(()=>{let active=true;if(!ticketId){setData(null);return;}const query=`?vehicle_id=${vehicleId}&ticket_id=${encodeURIComponent(ticketId)}`;
 api<Details>(`/details${query}`).then(d=>{if(active)setData(d)}).catch(e=>{if(active)setError((e as Error).message)});return()=>{active=false};},[vehicleId,ticketId]);
 const act=async(path:string,body:object,message:string)=>{setBusy(true);setError("");setNotice("");try{await api(path,body);await load();await onSaved();setNotice(message)}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 if(!ticketId)return <div className={styles.panel}><h3>Operational Control</h3><p>Select a ticket to manage follow-ups.</p></div>;
 const ref={vehicle_id:vehicleId,ticket_id:ticketId};
 const openActions=data?.actions.filter(x=>x.status==="open")||[];
 const activeBlockers=data?.blockers.filter(x=>x.status==="active")||[];
 const checks=new Set(data?.release.filter(x=>x.checked).map(x=>x.item_key)||[]);
 const ready=RELEASE.every(([key])=>checks.has(key));
 const next=data?.status.availability_status==="VOR"?"Operational":"VOR";
 return <section className={styles.panel} aria-label="Case operational control">
  <div className={styles.heading}><div><h3>Operational Control</h3><small>{openActions.length} actions · {activeBlockers.length} blockers · {data?.documents.filter(x=>x.status!=="verified").length??0} documents pending</small></div></div>
  {error&&<p className={styles.error} role="alert">{error}</p>}{notice&&<p role="status" className={styles.notice}>{notice}</p>}
  <nav className={styles.tabs} aria-label="Operational control sections">
   {([ ["actions","Actions"],["blockers","Blockers"],["documents","Documents"],["release","Release"],["status","Status"],["audit","Audit"]] as const).map(([id,name])=><button type="button" key={id} aria-pressed={section===id} className={section===id?styles.selected:""} onClick={()=>setSection(id)}>{name}</button>)}
  </nav>
  {section==="actions"&&<div className={styles.body}>
    <h4>Next actions</h4>
    {openActions.map(x=><div key={x.id} className={styles.record}><div><strong>{x.title}</strong><small>{x.owner} · Due {x.due_at}{x.due_at<today()?" · OVERDUE":""}</small></div><button disabled={busy} onClick={()=>void act("/actions/complete",{...ref,id:x.id},"Action completed")}>Done</button></div>)}
    {openActions.length===0&&<p>No open actions.</p>}
    <form className={styles.form} onSubmit={(e:FormEvent)=>{e.preventDefault();void act("/actions",{...ref,title,owner,due_at:due},"Action saved");setTitle("")}}>
      <label>Next action<input required minLength={3} maxLength={220} value={title} onChange={e=>setTitle(e.target.value)} placeholder="Request inspection update"/></label>
      <label>Owner<input required minLength={2} maxLength={100} value={owner} onChange={e=>setOwner(e.target.value)} placeholder="Fleet team member"/></label>
      <label>Deadline<input required type="date" value={due} onChange={e=>setDue(e.target.value)}/></label>
      <button disabled={busy} type="submit">+ Add action</button>
    </form>
   </div>}
  {section==="blockers"&&<div className={styles.body}><h4>Active blockers</h4>
    {activeBlockers.map(x=><div className={styles.record} key={x.id}><div><strong>{x.kind}</strong><small>{x.detail}</small></div><button disabled={busy} onClick={()=>void act("/blockers/resolve",{...ref,id:x.id},"Blocker resolved")}>Resolve</button></div>)}
    {activeBlockers.length===0&&<p>No active blockers.</p>}
    <form className={styles.form} onSubmit={e=>{e.preventDefault();void act("/blockers",{...ref,kind:blockerType,detail:blockerText},"Blocker recorded");setBlockerText("")}}>
      <label>Reason<select value={blockerType} onChange={e=>setBlockerType(e.target.value)}>{BLOCKERS.map(x=><option key={x}>{x}</option>)}</select></label>
      <label>Details<textarea required minLength={3} maxLength={500} value={blockerText} onChange={e=>setBlockerText(e.target.value)} placeholder="What is delaying the case?"/></label>
      <button disabled={busy} type="submit">+ Record blocker</button>
    </form></div>}
  {section==="documents"&&<div className={styles.body}><h4>Post-repair documents</h4>
    {data?.documents.map(d=><div className={styles.record} key={d.id}><div><strong>{d.kind}</strong><small>{d.reference||"No reference"}</small></div><select disabled={busy} aria-label={`Status of ${d.kind}`} value={d.status} onChange={e=>void act("/documents/status",{...ref,id:d.id,status:e.target.value},"Document updated")}>
      <option value="missing">Missing</option><option value="received">Received</option><option value="verified">Verified</option></select></div>)}
    <form className={styles.form} onSubmit={e=>{e.preventDefault();void act("/documents",{...ref,kind:docType,reference:docRef,status:docStatus},"Document recorded");setDocRef("")}}>
      <label>Document<select value={docType} onChange={e=>setDocType(e.target.value)}>{DOCUMENTS.map(x=><option key={x}>{x}</option>)}</select></label>
      <label>Reference (metadata only)<input value={docRef} maxLength={180} onChange={e=>setDocRef(e.target.value)} placeholder="Supplier document reference"/></label>
      <label>Status<select value={docStatus} onChange={e=>setDocStatus(e.target.value)}><option value="missing">Missing</option><option value="received">Received</option><option value="verified">Verified</option></select></label>
      <button disabled={busy} type="submit">+ Record document</button>
    </form></div>}
  {section==="release"&&<div className={styles.body}><h4>Vehicle release checks</h4><p>These checks are recorded independently of the repair-stage checklist.</p>
    {RELEASE.map(([key,label])=><label key={key} className={styles.check}><input disabled={busy} type="checkbox" checked={checks.has(key)} onChange={e=>void act("/release",{...ref,key,checked:e.target.checked},"Release check saved")}/><span>{label}</span></label>)}
    <p className={ready?styles.notice:styles.warning}>{ready?"Release checklist complete":"Release checklist incomplete"}</p></div>}
  {section==="status"&&<div className={styles.body}><h4>Manual status confirmation</h4><p>Current: <strong>{data?.status.availability_status}</strong>. Status is never changed automatically by workflow progression.</p>
    <label className={styles.check}><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>I confirm that I am recording the Fleet Department decision.</span></label>
    <label>Reason<textarea required minLength={5} maxLength={400} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Explain why the recorded status should change"/></label>
    {!ready&&next==="Operational"&&<label className={styles.check}><input type="checkbox" checked={override} onChange={e=>setOverride(e.target.checked)}/><span>Proceed despite incomplete release checks (explicit override, recorded in audit)</span></label>}
    <button disabled={busy||!confirmed||reason.trim().length<5||(!ready&&next==="Operational"&&!override)} onClick={()=>void act("/status",{...ref,new_status:next,reason,confirmed,override_incomplete_release:override},"Manual status recorded").then(()=>{setConfirmed(false);setReason("");setOverride(false)})}>Confirm {next} status</button>
  </div>}
  {section==="audit"&&<div className={styles.body}><h4>Recent operational audit</h4>
    {data?.skips.map(s=><div key={s.stage_index} className={styles.record}><div><strong>Stage {s.stage_index+1} — Not required</strong><small>{s.reason} · {s.actor}</small></div></div>)}
    {data?.audit.map((a,i)=><div key={`${a.created_at}-${i}`} className={styles.record}><div><strong>{a.action.replaceAll("_"," ")}</strong><small>{a.details} · {a.created_at}</small></div></div>)}
  </div>}
  <details className={styles.skip}><summary>Mark current stage as Not required</summary><label>Recorded by<input value={skipActor} maxLength={100} onChange={e=>setSkipActor(e.target.value)}/></label><label>Justification<textarea value={skipReason} maxLength={400} minLength={8} onChange={e=>setSkipReason(e.target.value)} placeholder="Explain why this stage is not applicable"/></label><button disabled={busy||skipReason.trim().length<8||skipActor.trim().length<2} onClick={()=>void act("/skip",{...ref,actor:skipActor,reason:skipReason},"Stage marked Not required").then(()=>setSkipReason(""))}>Skip current stage with reason</button></details>
 </section>;
}
