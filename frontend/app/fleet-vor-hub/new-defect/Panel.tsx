"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import styles from "./new-defect.module.css";

type Vehicle = {id:number;registration:string;model:string;garage:string;availability_status:string;is_archived:number};
type IntakeOptions = {vehicles:Vehicle[];reasons:string[];pathways:string[]};
type IntakeResult = {case_id:number;ticket_id:string;registration:string;pathway:string;requires_pts_workflow:boolean;availability_changed:boolean;repeated:boolean};

const PATHWAYS = [
  {value:"standard",name:"Standard Defect",sub:"Repair co-ordinated by PTS Fleet · 8-stage workflow"},
  {value:"tyres",name:"Wheels / Tyres",sub:"Managed by the HOTH team · no PTS repair workflow"},
  {value:"windscreen",name:"Windscreens",sub:"Managed by the HOTH team · no PTS repair workflow"},
];

async function request<T>(path:string,options?:RequestInit):Promise<T>{
  const response=await fetch(`/api/vor/intake${path}`,{
    cache:"no-store",credentials:"same-origin",...options,
    headers:{"Content-Type":"application/json",...options?.headers},
  });
  const result=await response.json().catch(()=>({detail:"Unable to read response"}));
  if(!response.ok)throw new Error(typeof result.detail==="string"?result.detail:`HTTP ${response.status}`);
  return result as T;
}

export default function NewDefectPanel({navigate,onRegistered}:{navigate:(section:"workspace"|"process")=>void;onRegistered?:(registration:string)=>void}){
  const [options,setOptions]=useState<IntakeOptions|null>(null);
  const [error,setError]=useState("");
  const [saving,setSaving]=useState(false);
  const [saved,setSaved]=useState<IntakeResult|null>(null);
  const [vehicle,setVehicle]=useState("");
  const [pathway,setPathway]=useState("standard");
  const [reason,setReason]=useState("");
  const [description,setDescription]=useState("");
  const [reference,setReference]=useState("");
  const [source,setSource]=useState("outlook");
  const [reportedVor,setReportedVor]=useState(true);
  const [roadside,setRoadside]=useState(false);
  const [requestId,setRequestId]=useState("");
  const refresh=useCallback(async()=>{setOptions(await request<IntakeOptions>("/options"));},[]);
  useEffect(()=>{refresh().catch(e=>setError((e as Error).message));},[refresh]);
  async function submit(event:FormEvent){
    event.preventDefault();setError("");setSaving(true);
    // Reuse the same idempotency key for network retries; reset only for a new case.
    const id=requestId || crypto.randomUUID();setRequestId(id);
    try{
      const result=await request<IntakeResult>("/defects",{method:"POST",body:JSON.stringify({
        vehicle_id:Number(vehicle),pathway,reason,description,hoth_reference:reference,
        source,reported_vor:reportedVor,roadside_reported:roadside,request_id:id,
      })});
      setSaved(result);onRegistered?.(result.registration);
    }catch(e){setError((e as Error).message)}finally{setSaving(false)}
  }
  function reset(){setSaved(null);setVehicle("");setPathway("standard");setReason("");setDescription("");setReference("");setSource("outlook");setReportedVor(true);setRoadside(false);setRequestId("");setError("")}
  return <section className={styles.page}>
    <header className={styles.header}>
      <div><span className={styles.eyebrow}>Fleet Operations · v2 · Synthetic demonstration</span><h1>Register a defect</h1><p>Log an OSD / HOTH notification for PTS Fleet tracking. External systems are not connected.</p></div>
      
    </header>
    {saved?<section className={styles.success} role="status">
      <div className={styles.successIcon}>✓</div><div><h2>Defect registered</h2><p>{saved.registration} · PTS ticket <strong>{saved.ticket_id}</strong> · Case #{saved.case_id}</p>
      <p>{saved.requires_pts_workflow?"Standard Defect workflow created with 8 stages.":"Specialist case recorded. The HOTH team manages the repair; no PTS stages created."}</p>
      <p><strong>Recorded vehicle availability was not changed.</strong> Fleet Department must confirm any change separately.</p>
      <div className={styles.actions}><button className={styles.primary} type="button" onClick={()=>navigate("workspace")}>View in Fleet Workspace →</button><button type="button" onClick={reset}>Register another defect</button></div></div>
    </section>:<div className={styles.layout}>
      <section className={styles.formCard}>
        <h2>New defect notification</h2>
        <p className={styles.intro}>Enter the details from OSD / Outlook. The new case will appear in the existing communication workspace.</p>
        {error&&<p role="alert" className={styles.error}>{error}</p>}
        <form onSubmit={e=>void submit(e)} className={styles.form}>
          <label>Vehicle <span>*</span><select required value={vehicle} onChange={e=>setVehicle(e.target.value)}><option value="">Select vehicle from Fleet Register…</option>{options?.vehicles.filter(v=>!v.is_archived).map(v=><option key={v.id} value={v.id}>{v.registration} — {v.model} ({v.garage})</option>)}</select></label>
          <div className={styles.two}><label>HOTH reference <span>*</span><input required maxLength={80} minLength={2} placeholder="HOTH-12345" value={reference} onChange={e=>setReference(e.target.value)}/></label>
            <label>Notification received via<select value={source} onChange={e=>setSource(e.target.value)}><option value="outlook">Outlook email (simulated)</option><option value="manual">Manual notification</option></select></label></div>
          <fieldset className={styles.pathways}><legend>Defect pathway <span>*</span></legend><div className={styles.pathwayOptions}>{PATHWAYS.map(p=><label key={p.value} className={`${styles.pathwayCard} ${pathway===p.value?styles.selected:""}`}><input type="radio" name="pathway" checked={pathway===p.value} onChange={()=>setPathway(p.value)}/><strong>{p.name}</strong><small>{p.sub}</small></label>)}</div></fieldset>
          <fieldset className={styles.reasons}><legend>High-level VOR reason <span>*</span></legend><div className={styles.reasonGrid}>{(options?.reasons||[]).filter(r=>!/COMMS|Misfuelled/i.test(r)).map(r=><label key={r} className={`${styles.reasonCard} ${reason===r?styles.reasonSelected:""}`}><input type="radio" name="vor-reason" value={r} required checked={reason===r} onChange={()=>setReason(r)}/><span>{r}</span></label>)}</div>{!reason&&<small className={styles.reasonHelp}>Choose one reason to continue.</small>}</fieldset>
          <label>Defect description <span>*</span><textarea minLength={3} maxLength={2000} rows={4} required placeholder="Describe the vehicle defect reported by OSD…" value={description} onChange={e=>setDescription(e.target.value)}/></label>
          <div className={styles.checks}><label><input type="checkbox" checked={reportedVor} onChange={e=>setReportedVor(e.target.checked)}/><span>Reported as Vehicle Off Road</span></label><label><input type="checkbox" checked={roadside} onChange={e=>setRoadside(e.target.checked)}/><span>Vehicle broken down roadside</span></label></div>
          {roadside&&<div className={styles.info}>OSD / HOTH organises roadside recovery. After the vehicle reaches the repair provider, the usual defect-handling process continues.</div>}
          <div className={styles.footer}><button disabled={saving||!options||!vehicle||!reason} type="submit">{saving?"Registering…":"Register defect →"}</button></div>
        </form>
      </section>

    </div>}
  </section>;
}
