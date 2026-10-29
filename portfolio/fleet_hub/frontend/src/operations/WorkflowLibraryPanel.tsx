"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./workflow-library.module.css";

type Workflow = {code:string;name:string;steps:string[];tickets_using:number;custom:boolean};
type Response = {workflows:Workflow[]};
const ROOT="/api/vor/workflow-admin";

async function api<T>(route:string,body?:object):Promise<T>{
  const response=await fetch(ROOT+route,{credentials:"same-origin",cache:"no-store",
    ...(body ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)} : {})});
  const json=await response.json().catch(()=>({detail:`HTTP ${response.status}`}));
  if(!response.ok)throw new Error(typeof json.detail==="string"?json.detail:`HTTP ${response.status}`);
  return json as T;
}

export default function WorkflowLibraryPanel(){
  const [workflows,setWorkflows]=useState<Workflow[]>([]);
  const [selected,setSelected]=useState("");
  const [name,setName]=useState(""); const [first,setFirst]=useState("Defect registered");
  const [newStage,setNewStage]=useState("");
  const [busy,setBusy]=useState(false); const [error,setError]=useState(""); const [notice,setNotice]=useState("");
  const refresh=useCallback(async()=>{
    const data=await api<Response>("");
    setWorkflows(data.workflows);
    setSelected(old=>data.workflows.some(w=>w.code===old)?old:(data.workflows[0]?.code||""));
  },[]);
  useEffect(()=>{let active=true;void Promise.resolve().then(()=>{if(active)return refresh()}).catch(e=>{if(active)setError((e as Error).message)});return()=>{active=false}},[refresh]);
  const active=workflows.find(w=>w.code===selected);
  const run=async(task:()=>Promise<unknown>,message:string)=>{
    setBusy(true);setError("");setNotice("");
    try{await task();await refresh();setNotice(message)}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  };
  const create=()=>{if(name.trim().length<3||first.trim().length<3)return;
    void run(async()=>{const w=await api<{code:string}>("/create",{name:name.trim(),first_stage:first.trim()});setSelected(w.code);setName("")},"Workflow created. Available for future ticket scenarios.");
  };
  const editName=()=>{if(!active)return;const next=window.prompt("Workflow name",active.name);if(next===null||next===active.name)return;
    void run(()=>api("/rename",{code:active.code,name:next}),"Workflow renamed.");};
  const editStage=(index:number)=>{if(!active)return;const next=window.prompt("Stage label",active.steps[index]);if(next===null||next===active.steps[index])return;
    void run(()=>api("/stage/edit",{code:active.code,index,label:next}),"Stage updated for future use.");};
  const deleteStage=(index:number)=>{if(!active)return;
    if(!window.confirm(`Delete stage ${index+1}: ${active.steps[index]}? Existing ticket usage will be checked and deletion rejected if any dependent stage exists.`))return;
    void run(()=>api("/stage/delete",{code:active.code,index}),"Unused stage deleted.");};
  const deleteWorkflow=()=>{if(!active)return;
    if(!window.confirm(`Delete workflow “${active.name}”? The server will refuse if any ticket uses it, including closed tickets.`))return;
    void run(()=>api("/delete",{code:active.code}),"Unused workflow deleted.");};
  return <section className={styles.library} aria-label="Workflow template library">
    <div className={styles.heading}><div><span className={styles.eyebrow}>WORKFLOW LIBRARY</span>
      <h2>Repair workflow templates</h2><p>Create workflows and their stages. Changes affect new assignments, not existing ticket history.</p></div>
      <span className={styles.count}>{workflows.length} templates</span>
    </div>
    {error&&<p className={styles.error} role="alert">{error}</p>}
    {notice&&<p className={styles.notice} role="status">{notice}</p>}
    <div className={styles.newFlow}>
      <label>New workflow name<input value={name} onChange={(e:{target:{value:string}})=>setName(e.target.value)} maxLength={100} placeholder="e.g. Warranty repair"/></label>
      <label>First stage<input value={first} onChange={(e:{target:{value:string}})=>setFirst(e.target.value)} maxLength={100}/></label>
      <button type="button" onClick={create} disabled={busy||name.trim().length<3||first.trim().length<3}>+ Create workflow</button>
    </div>
    <div className={styles.content}>
      <aside className={styles.list} aria-label="Available workflows">
        {workflows.map(w=><button key={w.code} type="button" disabled={busy} onClick={()=>setSelected(w.code)} aria-pressed={w.code===selected} className={w.code===selected?styles.selected:""}>
          <strong>{w.name}</strong><small>{w.steps.length} stages · {w.tickets_using} tickets</small>
        </button>)}
      </aside>
      <div className={styles.details}>{active?<>
        <div className={styles.templateHeader}><div><h3>{active.name}</h3><small>Code: {active.code} · {active.tickets_using} existing tickets</small></div>
          <div className={styles.actions}><button type="button" disabled={busy} onClick={editName}>Rename</button><button type="button" className={styles.danger} disabled={busy} onClick={deleteWorkflow}>Delete workflow</button></div></div>
        <ol className={styles.stages}>{active.steps.map((stage,index)=><li key={`${active.code}-${index}`}><span className={styles.num}>{String(index+1).padStart(2,"0")}</span><strong>{stage}</strong>
          <button type="button" disabled={busy} onClick={()=>editStage(index)} aria-label={`Rename stage ${stage}`}>Edit</button>
          <button type="button" disabled={busy} className={styles.danger} onClick={()=>deleteStage(index)} aria-label={`Delete stage ${stage}`}>Delete</button></li>)}</ol>
        <div className={styles.addStage}><input aria-label="New stage name" placeholder="New stage name" value={newStage} maxLength={100} onChange={(e:{target:{value:string}})=>setNewStage(e.target.value)}/>
          <button type="button" disabled={busy||newStage.trim().length<3} onClick={()=>void run(async()=>{await api("/stage/add",{code:active.code,label:newStage.trim()});setNewStage("")},"Stage added for future assignments.")}>+ Add stage</button></div>
        {active.tickets_using>0&&<p className={styles.hint}>This template is referenced by existing tickets. Deletion of used stages or the workflow is blocked, preserving their audit history.</p>}
      </>:<p>Select or create a workflow.</p>}</div>
    </div>
  </section>;
}
