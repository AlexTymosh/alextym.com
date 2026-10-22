"use client";
import {useEffect,useState} from "react";
import styles from "./operations.module.css";
type Item={id:number;registration:string;vehicle_id:number;ticket_id:string;title?:string;owner?:string;due_at?:string;kind?:string;detail?:string;status:string};
type Queue={actions:Item[];blockers:Item[]};
export default function OperationsQueuePanel({onOpenVehicle}:{onOpenVehicle:(registration:string)=>void}){
 const [data,setData]=useState<Queue|null>(null);const [error,setError]=useState("");const [filter,setFilter]=useState("all");
 useEffect(()=>{fetch("/api/vor/ops/queue",{credentials:"same-origin",cache:"no-store"}).then(async r=>{const j=await r.json();if(!r.ok)throw new Error(j.detail||`HTTP ${r.status}`);setData(j as Queue)}).catch(e=>setError((e as Error).message))},[]);
 const rows=[...(data?.actions||[]).map(x=>({...x,type:"Action"})),...(data?.blockers||[]).map(x=>({...x,type:"Blocker"}))]
  .filter(x=>filter==="all"||x.type.toLowerCase()===filter);
 return <section className={styles.settingsPage}><header><h2>Actions & Blockers</h2><p>Live operational queue across active vehicles. Select a registration to open its workspace.</p></header>
 {error&&<p role="alert" className={styles.error}>{error}</p>}
 <div className={styles.tabs}>{(["all","action","blocker"] as const).map(x=><button key={x} className={filter===x?styles.selected:""} onClick={()=>setFilter(x)}>{x==="all"?"All":x==="action"?"Actions":"Blockers"}</button>)}</div>
 <article className={styles.settingStage}>
  <h3>{rows.length} open items</h3>
  {rows.length===0&&<p>No outstanding items in this filter.</p>}
  {rows.map(x=><div key={`${x.type}-${x.id}`} className={styles.record}>
    <div><strong>{x.type}: {x.title||x.kind}</strong><small>{x.detail||`${x.owner||"Unassigned"} · Due ${x.due_at||"not set"}`}</small></div>
    <button onClick={()=>onOpenVehicle(x.registration)}>{x.registration}</button>
   </div>)}
 </article></section>;
}
