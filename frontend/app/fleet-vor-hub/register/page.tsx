"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
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
  for(let i=0;i<bytes.length;i+=8192){text+=String.fromCharCode(...bytes.subarray(i,i+8192));}
  return btoa(text);
}

export default function VehicleRegister(){
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
  const refresh=useCallback(async()=>{setData(await call<Data>("/register"));},[]);
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[refresh]);
  async function perform(work:()=>Promise<void>){setBusy(true);setError("");setNotice("");try{await work();await refresh();}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  function add(e:FormEvent){e.preventDefault();void perform(async()=>{const added=await call<{registration:string}>("/vehicles",{registration:reg,model,garage});setNotice(`Vehicle ${added.registration} added`);setReg("");setModel("");setGarage("")})}
  async function doPreview(){if(!selected)return;await perform(async()=>{const b64=await toBase64(selected);setEncoded(b64);const p=await call<Preview>("/imports/preview",{filename:selected.name,content_b64:b64,mode});setPreview(p);setNotice(`Preview: ${p.count} valid rows, ${p.errors.length} errors`)})}
  async function doCommit(){if(!preview||!selected||!encoded)return;await perform(async()=>{const result=await call<{summary:Record<string,number>;repeated:boolean}>("/imports/commit",{filename:selected.name,content_b64:encoded,mode,digest:preview.digest});setNotice(result.repeated?"This file was already imported":`Imported ${result.summary.insert} · Updated ${result.summary.update} · Skipped ${result.summary.skip}`);setPreview(null);setEncoded("");setSelected(null)})}
  const vehicles=data?.vehicles.filter(x=>Boolean(x.is_archived)===archived)||[];
  return <main className={styles.page}>
    <header className={styles.head}><div><small>Fleet VOR Hub · v2</small><h1>Vehicle Register</h1><p>Manage synthetic vehicle records and review imports. No defect case is created automatically.</p></div><Link href="/fleet-vor-hub">← Back to workspace</Link></header>
    {error&&<div role="alert" className={styles.error}>{error}</div>}
    {notice&&<div role="status" className={styles.notice}>{notice}</div>}
    <div className={styles.grid}>
      <section className={styles.card}><h2>Add vehicle</h2><p>Add an asset without changing its availability or creating a VOR case.</p><form onSubmit={add} className={styles.form}>
        <label>Registration<input required maxLength={32} placeholder="GX24 KLM" value={reg} onChange={e=>setReg(e.target.value)}/></label>
        <label>Make / model<input required maxLength={120} placeholder="Ford Transit 350" value={model} onChange={e=>setModel(e.target.value)}/></label>
        <label>Workshop / depot<input required maxLength={100} placeholder="Basingstoke" value={garage} onChange={e=>setGarage(e.target.value)}/></label>
        <button disabled={busy} type="submit">Add vehicle</button>
      </form></section>
      <section className={styles.card}><h2>Import CSV / Excel</h2><p>Required columns: Registration, Model, Garage. First XLSX sheet is used; UTF-8 CSV supported. Maximum 2 MB / 2,000 rows.</p>
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
      </section>
    </div>
    <section className={styles.card}><div className={styles.titleRow}><div><h2>Fleet assets</h2><p>{vehicles.length} {archived?"archived":"active"} records</p></div><button className={styles.secondary} onClick={()=>setArchived(x=>!x)}>{archived?"Show active":"Show archived"}</button></div>
      <div className={styles.tableWrap}><table><thead><tr><th>Registration</th><th>Model</th><th>Garage</th><th>KEY2 demo status</th><th>Cases</th><th>Action</th></tr></thead><tbody>{vehicles.map(v=><tr key={v.id}><td><strong>{v.registration}</strong></td><td>{v.model}</td><td>{v.garage}</td><td><span className={v.availability_status==="VOR"?styles.vor:styles.available}>{v.availability_status}</span></td><td>{data?.cases.filter(c=>c.vehicle_id===v.id).length||0}</td><td><button className={styles.secondary} disabled={busy} onClick={()=>void perform(async()=>{await call(`/vehicles/${v.id}/archive`,{archived:!v.is_archived});setNotice(v.is_archived?"Asset restored":"Asset archived; history preserved")})}>{v.is_archived?"Restore":"Archive"}</button></td></tr>)}</tbody></table></div>
    </section>
    <section className={styles.card}><h2>Recorded status history</h2><p>Initial snapshots and explicit manual Fleet confirmations. This is not a live KEY2 connection.</p>
      <div className={styles.tableWrap}><table><thead><tr><th>When (UTC)</th><th>Vehicle</th><th>From</th><th>To</th><th>Actor / source</th><th>Reason</th></tr></thead><tbody>{data?.statuses.slice(0,60).map(x=><tr key={x.id}><td>{x.recorded_at}</td><td>{(data?.vehicles||[]).find(v=>v.id===x.vehicle_id)?.registration||x.vehicle_id}</td><td>{x.old_status||"—"}</td><td>{x.new_status}</td><td>{x.actor}</td><td>{x.reason||"Baseline"}</td></tr>)}</tbody></table></div>
    </section>
  </main>;
}
