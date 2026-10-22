"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import styles from "./reconciliation.module.css";

type Source="hoth"|"fleet";
type Batch={id:number;source:Source;label:string;row_count:number;imported_at:string;source_as_of:string;is_demo:number};
type Issue={id:number;run_id:number;registration:string;category:string;hoth_status:string|null;fleet_status:string|null;local_status:string|null;hoth_reference:string|null;fleet_reference:string|null;resolution:string;owner:string;note:string;updated_at:string|null};
type Run={id:number;created_at:string;hoth_batch_id:number;fleet_batch_id:number;matched_count:number};
type Audit={id:number;issue_id:number;old_resolution:string;new_resolution:string;actor:string;owner:string;note:string;recorded_at:string};
type BatchPayload={batches:Batch[];latest:Record<Source,Batch|null>};
type SourceInfo={batch_id:number;label:string;source_as_of:string;stale:boolean;age_hours:number};
type Detail={run:Run|null;issues:Issue[];audit:Audit[];sources:Record<Source,SourceInfo>|null};
type History=Run & {issue_count:number};
const API="/api/vor/reconciliation";
const sourceNames:Record<Source,string>={hoth:"HOTH snapshot",fleet:"Fleet register snapshot"};
const categories:Record<string,string>={status_mismatch:"Different status",local_mismatch:"Local register differs",missing_hoth:"Absent from HOTH",missing_fleet:"Absent from Fleet snapshot",unregistered:"Unknown vehicle"};
const decisions:Record<string,string>={open:"Open",acknowledged:"Acknowledged",resolved:"Resolved",not_an_error:"Not an error"};
const sample="Registration,Status,Reference,Reason\nGX24 KLM,VOR,DEMO-001,Mechanical\nAB26 XYZ,Operational,DEMO-002,Returned to service\n";

async function api<T>(path:string,body?:unknown):Promise<T>{
 const r=await fetch(API+path,{credentials:"same-origin",cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
 const payload=await r.json().catch(()=>({detail:`HTTP ${r.status}`}));
 if(!r.ok)throw new Error(typeof payload.detail==="string"?payload.detail:`HTTP ${r.status}`);
 return payload as T;
}
const dateStr=(s:string|null|undefined)=>s?s.replace("T"," ").replace(/\+00:00|Z/,"").slice(0,16):"—";

function Status({value}:{value:string|null}){return <span className={`${styles.status} ${value==="VOR"?styles.vor:value==="Operational"?styles.operational:styles.missing}`}>{value??"Missing"}</span>}

function ReviewRow({issue,actor,onSaved}:{issue:Issue;actor:string;onSaved:()=>Promise<void>}){
 const [decision,setDecision]=useState(issue.resolution);
 const [owner,setOwner]=useState(issue.owner);
 const [note,setNote]=useState(issue.note);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const save=async()=>{setBusy(true);setError("");try{await api("/review",{issue_id:issue.id,decision,owner,actor,note});await onSaved()}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 return <tr>
  <td><strong>{issue.registration}</strong><small>{categories[issue.category]??issue.category}</small></td>
  <td><Status value={issue.hoth_status}/><small>{issue.hoth_reference??""}</small></td>
  <td><Status value={issue.fleet_status}/><small>{issue.fleet_reference??""}</small></td>
  <td><Status value={issue.local_status}/></td>
  <td><select aria-label={`Review decision for ${issue.registration}`} value={decision} onChange={e=>setDecision(e.target.value)}>{Object.entries(decisions).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></td>
  <td><input aria-label={`Owner for ${issue.registration}`} value={owner} maxLength={100} placeholder="Owner" onChange={e=>setOwner(e.target.value)}/></td>
  <td><textarea aria-label={`Review notes for ${issue.registration}`} rows={2} maxLength={750} value={note} placeholder="Reason / evidence" onChange={e=>setNote(e.target.value)}/>{error&&<small className={styles.error}>{error}</small>}</td>
  <td><button disabled={busy||actor.trim().length<2||(!note.trim()&&decision!=="open")} className={styles.smallButton} type="button" onClick={()=>void save()}>{busy?"Saving…":"Save"}</button></td>
 </tr>;
}

export default function ReconciliationPanel(){
 const [batches,setBatches]=useState<BatchPayload|null>(null);
 const [detail,setDetail]=useState<Detail>({run:null,issues:[],audit:[],sources:null});
 const [runs,setRuns]=useState<History[]>([]);
 const [selectedRun,setSelectedRun]=useState<string>("");
 const [source,setSource]=useState<Source>("hoth");
 const [file,setFile]=useState<File|null>(null);
 const [label,setLabel]=useState("");
 const [hothId,setHothId]=useState("");
 const [fleetId,setFleetId]=useState("");
 const [filter,setFilter]=useState("all");
 const [query,setQuery]=useState("");
 const [actor,setActor]=useState("Fleet reviewer");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [message,setMessage]=useState("");
 const refresh=useCallback(async()=>{const b=await api<BatchPayload>("/batches");const h=await api<History[]>("/runs");const d=await api<Detail>(`/latest${selectedRun?`?run_id=${selectedRun}`:""}`);setBatches(b);setRuns(h);setDetail(d);setHothId(v=>v||(b.latest.hoth?String(b.latest.hoth.id):""));setFleetId(v=>v||(b.latest.fleet?String(b.latest.fleet.id):""));},[selectedRun]);
 useEffect(()=>{void refresh().catch(e=>setError((e as Error).message))},[refresh]);
 const counts=useMemo(()=>({open:detail.issues.filter(x=>x.resolution==="open").length,reviewed:detail.issues.filter(x=>x.resolution!=="open").length}),[detail.issues]);
 const rows=useMemo(()=>detail.issues.filter(i=>(filter==="all"||i.resolution===filter)&&`${i.registration} ${i.category} ${i.owner}`.toLowerCase().includes(query.toLowerCase())).sort((a,b)=>Number(a.resolution!=="open")-Number(b.resolution!=="open")),[detail.issues,filter,query]);
 const upload=async()=>{if(!file)return;setBusy(true);setError("");setMessage("");try{
   if(!/\.csv$/i.test(file.name)||file.size>550_000)throw new Error("Select a CSV file (maximum 550 KB)");
   const csv_text=await file.text();const result=await api<{batch_id:number;row_count:number}>("/imports",{source,label:label.trim()||file.name,source_as_of:new Date().toISOString(),csv_text});
   setMessage(`Imported ${result.row_count} rows into ${sourceNames[source]} · batch #${result.batch_id}. Run comparison to see differences.`);
   setFile(null);setLabel("");await refresh();if(source==="hoth")setHothId(String(result.batch_id));else setFleetId(String(result.batch_id));
 }catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 const compare=async()=>{setBusy(true);setError("");setMessage("");try{if(!hothId||!fleetId)throw new Error("Choose both source snapshots");const r=await api<{run_id:number;issue_count:number;matched_count:number}>("/compare",{hoth_batch_id:Number(hothId),fleet_batch_id:Number(fleetId)});setSelectedRun(String(r.run_id));setMessage(`Comparison #${r.run_id}: ${r.matched_count} matches; ${r.issue_count} review items.`);}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 const downloadTemplate=()=>{const url=URL.createObjectURL(new Blob([sample],{type:"text/csv;charset=utf-8"}));const a=document.createElement("a");a.href=url;a.download="reconciliation-sample.csv";a.click();URL.revokeObjectURL(url)};
 return <div className={styles.root}>
  <div className={styles.intro}><div><h2>Source reconciliation</h2><p>Compare independently recorded vehicle status snapshots. Differences are review items, not automatic errors.</p></div><span className={styles.demo}>SYNTHETIC DATA</span></div>
  {error&&<div className={styles.errorBox} role="alert">{error}</div>}{message&&<div className={styles.message} role="status">{message}</div>}
  <div className={styles.metrics}><div><small>Matched vehicles</small><strong>{detail.run?.matched_count??"—"}</strong></div><div><small>Open discrepancies</small><strong>{counts.open}</strong></div><div><small>Reviewed</small><strong>{counts.reviewed}</strong></div><div><small>Last comparison</small><strong className={styles.dateMetric}>{dateStr(detail.run?.created_at)}</strong></div></div>
  <div className={styles.controls}>
   <section className={styles.card}><h3>1. Source snapshots</h3><p>Sample snapshots are supplied for the demonstration; CSV files can replace either source independently.</p><div className={styles.twoColumns}>{(["hoth","fleet"] as Source[]).map(k=><label key={k}>{sourceNames[k]}<select value={k==="hoth"?hothId:fleetId} onChange={e=>k==="hoth"?setHothId(e.target.value):setFleetId(e.target.value)}>{(batches?.batches.filter(b=>b.source===k)||[]).map(b=><option key={b.id} value={b.id}>#{b.id} · {b.label} ({b.row_count})</option>)}</select></label>)}</div><button className={styles.primary} type="button" disabled={busy||!hothId||!fleetId} onClick={()=>void compare()}>{busy?"Working…":"Run comparison"}</button></section>
   <section className={styles.card}><h3>Import a snapshot</h3><div className={styles.twoColumns}><label>Source<select value={source} onChange={e=>setSource(e.target.value as Source)}><option value="hoth">HOTH</option><option value="fleet">Fleet register</option></select></label><label>Batch label<input value={label} maxLength={100} placeholder="e.g. Morning status report" onChange={e=>setLabel(e.target.value)}/></label></div><input aria-label="Snapshot CSV" type="file" accept=".csv,text/csv" onChange={e=>setFile(e.target.files?.[0]??null)}/><div className={styles.actions}><button type="button" onClick={downloadTemplate}>Download CSV example</button><button type="button" disabled={!file||busy} onClick={()=>void upload()}>Import snapshot</button></div><small>Columns: Registration, Status, Reference, Reason. No changes are made to vehicle status.</small></section>
  </div>
  <section className={styles.card}><div className={styles.tableHeading}><div><h3>Discrepancy queue</h3><p>{detail.run?`Run #${detail.run.id} · ${detail.issues.length} items for review`:"Select source snapshots and run the first comparison"}</p></div>{detail.run&&<div className={styles.actions}><a className={styles.export} href={`${API}/export.xlsx?run_id=${detail.run.id}`}>↓ Excel</a><a className={styles.export} href={`${API}/export.csv?run_id=${detail.run.id}`}>↓ CSV</a></div>}</div><div className={styles.filters}><input aria-label="Reviewer name" placeholder="Reviewer name" value={actor} maxLength={100} onChange={e=>setActor(e.target.value)}/><select aria-label="Comparison history" value={selectedRun} onChange={e=>setSelectedRun(e.target.value)}><option value="">Latest comparison</option>{runs.map(r=><option key={r.id} value={r.id}>Run #{r.id} · {dateStr(r.created_at)} · {r.issue_count} differences</option>)}</select><input aria-label="Search discrepancies" placeholder="Search registration, category or owner" value={query} onChange={e=>setQuery(e.target.value)}/><select aria-label="Filter review state" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All review states</option>{Object.entries(decisions).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></div>{detail.sources&&Object.entries(detail.sources).some(([,v])=>v.stale)&&<p className={styles.staleWarning}>Some selected source snapshots are over 48 hours old. Verify their timestamps before treating differences as actionable.</p>}<div className={styles.provenance}>{detail.sources&&(["hoth","fleet"] as Source[]).map(k=><span key={k}>{sourceNames[k]} as of {dateStr(detail.sources?.[k].source_as_of)}{detail.sources?.[k].stale?" · Stale":""}</span>)}</div><div className={styles.tableScroll}><table><thead><tr><th>Vehicle / difference</th><th>HOTH</th><th>Fleet snapshot</th><th>Local register</th><th>Review state</th><th>Owner</th><th>Notes</th><th></th></tr></thead><tbody>{rows.map(issue=><ReviewRow key={issue.id} issue={issue} actor={actor} onSaved={refresh}/>)}{rows.length===0&&<tr><td colSpan={8}>No discrepancies match these filters.</td></tr>}</tbody></table></div></section>
  {detail.audit.length>0&&<section className={styles.card}><h3>Review audit</h3><div className={styles.audit}>{detail.audit.slice(0,25).map(a=><div key={a.id}><strong>{a.actor}</strong><span>{a.old_resolution} → {a.new_resolution}</span><span>{a.note}</span><time>{dateStr(a.recorded_at)}</time></div>)}</div></section>}
 </div>;
}
