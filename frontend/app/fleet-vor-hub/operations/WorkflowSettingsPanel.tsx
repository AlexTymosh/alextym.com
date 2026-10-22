"use client";
import {useEffect,useState} from "react";
import styles from "./operations.module.css";
type Template={stage_index:number;item_key:string;label:string;required:boolean};
const stages=["Defect Registered","Diagnosis Scheduled","Awaiting Quotation","Repair Approval","Repair in Progress","Release Check","Operations Desk Closure","Post-Repair Documentation"];
export default function WorkflowSettingsPanel(){
 const [items,setItems]=useState<Template[]>([]);const [error,setError]=useState("");const [notice,setNotice]=useState("");const [busy,setBusy]=useState(false);
 useEffect(()=>{fetch("/api/vor/ops/templates",{credentials:"same-origin",cache:"no-store"}).then(async r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return await r.json() as {items:Template[]}}).then(r=>setItems(r.items)).catch(e=>setError((e as Error).message))},[]);
 const update=(index:number,changes:Partial<Template>)=>setItems(v=>v.map((x,i)=>i===index?{...x,...changes}:x));
 const save=async(item:Template)=>{setBusy(true);setError("");setNotice("");try{const r=await fetch("/api/vor/ops/templates",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({stage_index:item.stage_index,key:item.item_key,label:item.label,required:item.required})});const j=await r.json().catch(()=>({detail:"Error"}));if(!r.ok)throw new Error(j.detail||`HTTP ${r.status}`);setNotice("Template item saved. Existing completed-stage audit is preserved.")}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 return <section className={styles.settingsPage}><header><h2>Workflow Settings</h2><p>Edit checklist labels and which items are mandatory. Changes affect validation of future stage completions; previously completed stage audit is not rewritten.</p></header>
 {error&&<p role="alert" className={styles.error}>{error}</p>}{notice&&<p role="status" className={styles.notice}>{notice}</p>}
 {stages.map((name,index)=><article key={name} className={styles.settingStage}><h3>{String(index+1).padStart(2,"0")} · {name}</h3>
  {items.map((item,i)=>item.stage_index===index&&<div key={item.item_key} className={styles.settingItem}>
    <input aria-label={`Label for ${item.item_key}`} value={item.label} maxLength={100} onChange={e=>update(i,{label:e.target.value})}/>
    <label><input type="checkbox" checked={item.required} disabled={item.item_key==="diagnosis_date"} onChange={e=>update(i,{required:e.target.checked})}/> Required</label>
    <button disabled={busy||item.label.trim().length<3} onClick={()=>void save(item)}>Save</button>
  </div>)}
 </article>)}
 </section>;
}
