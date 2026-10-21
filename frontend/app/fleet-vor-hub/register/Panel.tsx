"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import styles from "./register.module.css";

type Vehicle = {id:number;registration:string;model:string;garage:string;availability_status:string;is_archived:number};
type Case = {id:number;vehicle_id:number;status:string;description:string;legacy_ticket_id:string|null};
type Status = {id:number;vehicle_id:number;old_status:string|null;new_status:string;actor:string;reason:string|null;recorded_at:string};
type Row = {registration:string;model:string;garage:string;action:string;row_number:string};
type Preview = {digest:string;filename:string;mode:string;count:number;errors:{row:string;error:string}[];preview:Row[];summary:Record<string,number>;repeated:boolean};
type Data = {vehicles:Vehicle[];cases:Case[];statuses:Status[];batches:{id:number;filename:string;row_count:number;created_at:string}[]};
const API="/api/vor/data";

async function call<T>(path:string,body?:object):Promise<T>{
  const res=await fetch(API+path,{credentials:"same-origin",cache:"no-store",method:body?"POST":"GET",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
  const data=await res.json().catch(()=>({detail:"Request failed"}));
  if(!res.ok)throw new Error(typeof data.detail==="string"?data.detail:`HTTP ${res.status}`);
  return data as T;
}

async function toBase64(file:File):Promise<string>{
  const bytes=new Uint8Array(await file.arrayBuffer());
  if(bytes.length>2_000_000)throw new Error("Maximum upload size is 2 MB");
  let text="";
  for(let i=0;i<bytes.length;i+=8192){text+=String.fromCharCode(...Array.from(bytes.subarray(i,i+8192)));}
  return btoa(text);
}

const SAMPLE_ROWS = [
  {registration:"AB26 XYZ", model:"Ford Transit 350", garage:"Basingstoke"},
  {registration:"CD25 KLM", model:"Mercedes Sprinter", garage:"Oxford"},
];
function downloadCsvTemplate(){
  const body=["Registration,Model,Garage", ...SAMPLE_ROWS.map(row=>[row.registration,row.model,row.garage].join(","))].join("\r\n")+"\r\n";
  const blob=new Blob(["\uFEFF",body],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");link.href=url;link.download="fleet-vehicle-import-template.csv";
  document.body.appendChild(link);link.click();link.remove();
  // The download has already been initiated; revoke after the click completes.
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export default function VehicleRegisterPanel({section,navigate}:{section:"register"|"add"|"import"|"status-history";navigate:(view:"register"|"add"|"import"|"status-history")=>void}){
  const [data,setData]=useState<Data|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [reg,setReg]=useState("");const [model,setModel]=useState("");const [garage,setGarage]=useState("");
  const [selected,setSelected]=useState<File|null>(null);
  const [encoded,setEncoded]=useState("");
  const [mode,setMode]=useState<"skip"|"update">("skip");
  const [preview,setPreview]=useState<Preview|null>(null);
  const [archived,setArchived]=useState(false);
  const [selectedVehicleId,setSelectedVehicleId]=useState<number|null>(null);
  const refresh=useCallback(async()=>{setData(await call<Data>("/register"));},[]);
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[refresh]);
  async function perform(work:()=>Promise<void>){setBusy(true);setError("");setNotice("");try{await work();await refresh();}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  function add(e:FormEvent){e.preventDefault();void perform(async()=>{const added=await call<{registration:string}>("/vehicles",{registration:reg,model,garage});setNotice(`Vehicle ${added.registration} added`);setReg("");setModel("");setGarage("")})}
  async function doPreview(){if(!selected)return;await perform(async()=>{const b64=await toBase64(selected);setEncoded(b64);const p=await call<Preview>("/imports/preview",{filename:selected.name,content_b64:b64,mode});setPreview(p);setNotice(`Preview: ${p.count} valid rows, ${p.errors.length} errors`)})}
  async function doCommit(){if(!preview||!selected||!encoded)return;await perform(async()=>{const result=await call<{summary:Record<string,number>;repeated:boolean}>("/imports/commit",{filename:selected.name,content_b64:encoded,mode,digest:preview.digest});setNotice(result.repeated?"This file was already imported":`Imported ${result.summary.insert} · Updated ${result.summary.update} · Skipped ${result.summary.skip}`);setPreview(null);setEncoded("");setSelected(null)})}
  const vehicles=data?.vehicles.filter(x=>Boolean(x.is_archived)===archived)||[];
  const focused=data?.vehicles.find(v=>v.id===selectedVehicleId);
  return <section className={styles.page}>
    <header className={styles.head}><div><small>FLEET DATA · SYNTHETIC DEMO</small><h1>{section==="register"?"Vehicle Register":section==="status-history"?"Recorded Status History":section==="add"?"Add Vehicle":"Import Vehicles"}</h1><p>{section==="register"?"Browse assets and manage archive status.":section==="status-history"?"A separate audit view of recorded fleet availability changes.":section==="add"?"Create a single vehicle record without starting a defect.":"Import fleet vehicles from a CSV or Excel workbook."}</p></div><nav className={styles.quickNav}><button type="button" onClick={()=>navigate("register")}>Vehicle Register</button><button type="button" onClick={()=>navigate("status-history")}>Status history</button><button type="button" onClick={()=>navigate("add")}>Add one</button><button type="button" onClick={()=>navigate("import")}>Bulk import</button></nav></header>
    {error&&<div role="alert" className={styles.error}>{error}</div>}
    {notice&&<div role="status" className={styles.notice}>{notice}</div>}
    {(section==="add"||section==="import")&&<div className={styles.grid}>
      {section==="add"&&<section className={styles.card}><h2>Add vehicle</h2><p>Add an asset without changing its availability or creating a VOR case.</p><form onSubmit={add} className={styles.form}>
        <label>Registration<input required maxLength={32} placeholder="GX24 KLM" value={reg} onChange={e=>setReg(e.target.value)}/></label>
        <label>Make / model<input required maxLength={120} placeholder="Ford Transit 350" value={model} onChange={e=>setModel(e.target.value)}/></label>
        <label>Workshop / depot<input required maxLength={100} placeholder="Basingstoke" value={garage} onChange={e=>setGarage(e.target.value)}/></label>
        <button disabled={busy} type="submit">Add vehicle</button>
      </form></section>}
      {section==="import"&&<section className={styles.card}><h2>Import CSV / Excel</h2><p>Required columns: Registration, Model, Garage. First XLSX sheet is used; UTF-8 CSV supported. Maximum 2 MB / 2,000 rows.</p>
        <div className={styles.sampleArea}>
          <div className={styles.sampleTitle}><div><strong>Example import file</strong><p>Use these column names in the first row of your CSV or Excel file.</p></div><button className={styles.secondary} type="button" onClick={downloadCsvTemplate}>↓ Download CSV template</button></div>
          <div className={styles.tableWrap}><table><thead><tr><th>Registration</th><th>Model</th><th>Garage</th></tr></thead><tbody>{SAMPLE_ROWS.map(r=><tr key={r.registration}><td>{r.registration}</td><td>{r.model}</td><td>{r.garage}</td></tr>)}</tbody></table></div>
        </div>
        <div className={styles.form}>
        <label>File<input type="file" accept=".csv,.xlsx" onChange={e=>{setSelected(e.target.files?.[0]||null);setPreview(null);setEncoded("")}}/></label>
        <label>Existing registrations<select value={mode} onChange={e=>{setMode(e.target.value as "skip"|"update");setPreview(null);setEncoded("")}}><option value="skip">Skip existing</option><option value="update">Update model and garage only</option></select></label>
        <button disabled={busy||!selected} type="button" onClick={()=>void doPreview()}>Preview import</button>
        {preview&&<div className={styles.preview}><strong>{preview.count} valid rows · {preview.errors.length} errors</strong><div>{Object.entries(preview.summary).map(([key,value])=><span key={key}>{key}: {value} · </span>)}</div>
         {preview.repeated&&<p>Already imported with this mode.</p>}
         {preview.errors.slice(0,12).map((r,i)=><p key={i} className={styles.error}>Row {r.row}: {r.error}</p>)}
         <div className={styles.rows}>{preview.preview.slice(0,20).map(r=><div key={r.row_number}>{r.registration} · {r.model} · {r.garage} <b>{r.action}</b></div>)}</div>
         <button disabled={busy||preview.errors.length>0||preview.repeated} type="button" onClick={()=>void doCommit()}>Confirm import</button>
        </div>}
        </div>
      </section>}
    </div>}
    {section==="register"&&<section className={styles.card}><div className={styles.titleRow}><div><h2>Fleet assets</h2><p>{vehicles.length} {archived?"archived":"active"} records</p></div><button className={styles.secondary} type="button" onClick={()=>{setArchived(x=>!x);setSelectedVehicleId(null)}}>{archived?"Show active":"Show archived"}</button></div>
      <div className={styles.tableWrap}><table><thead><tr><th>Registration</th><th>Model</th><th>Garage</th><th>Recorded status</th></tr></thead><tbody>{vehicles.map(v=><tr key={v.id}><td><button type="button" className={styles.assetLink} onClick={()=>setSelectedVehicleId(v.id)} aria-pressed={selectedVehicleId===v.id}>{v.registration}</button></td><td>{v.model}</td><td>{v.garage}</td><td><span className={v.availability_status==="VOR"?styles.vor:styles.available}>{v.availability_status}</span></td></tr>)}</tbody></table></div>
      {focused&&Boolean(focused.is_archived)===archived&&<div className={styles.assetToolbar}><div><strong>{focused.registration}</strong><p>{focused.model} · {focused.garage}. Select an asset to manage its archive status.</p></div><button className={styles.secondary} disabled={busy} type="button" onClick={()=>void perform(async()=>{await call(`/vehicles/${focused.id}/archive`,{archived:!focused.is_archived});setNotice(focused.is_archived?"Asset restored":"Asset archived; history preserved");setSelectedVehicleId(null)})}>{focused.is_archived?"Restore vehicle":"Archive vehicle"}</button></div>}
    </section>}
    {section==="status-history"&&<section className={styles.card}><h2>Recorded status history</h2><p>Initial snapshots and explicit manual Fleet confirmations. This is a local synthetic audit history.</p>
      <div className={styles.tableWrap}><table><thead><tr><th>When (UTC)</th><th>Vehicle</th><th>From</th><th>To</th><th>Actor / source</th><th>Reason</th></tr></thead><tbody>{data?.statuses.slice(0,60).map(x=><tr key={x.id}><td>{x.recorded_at}</td><td>{(data?.vehicles||[]).find(v=>v.id===x.vehicle_id)?.registration||x.vehicle_id}</td><td>{x.old_status||"—"}</td><td>{x.new_status}</td><td>{x.actor.replace(/\b(KEY2|NHS)\b/gi,"Fleet system")}</td><td>{(x.reason||"Baseline").replace(/\b(KEY2|NHS)\b/gi,"Fleet system")}</td></tr>)}</tbody></table></div>
    </section>}
  </section>;
}
