"use client";
import styles from "./signals.module.css";
export type OpsIndicator={actions:number;overdue:number;blockers:number;documents:number;docs_verified:number;release_ready:boolean;next_action:{title:string;owner:string;due_at:string}|null;stage_done:number;stage_total:number;stage_current?:string};
const empty:OpsIndicator={actions:0,overdue:0,blockers:0,documents:0,docs_verified:0,release_ready:false,next_action:null,stage_done:0,stage_total:0};
function Glyph({type}:{type:"task"|"block"|"doc"|"release"|"progress"}){
 const p={fill:"none",stroke:"currentColor",strokeWidth:1.8,strokeLinecap:"round" as const,strokeLinejoin:"round" as const};
 return <svg width="13" height="13" viewBox="0 0 24 24" aria-hidden="true" {...p}>
  {type==="task"&&<><rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 12 2 2 5-5"/></>}
  {type==="block"&&<><path d="M12 3 2 21h20L12 3Z"/><path d="M12 9v5m0 3v.2"/></>}
  {type==="doc"&&<><path d="M6 2h8l5 5v15H6z"/><path d="M14 2v5h5M9 12h7M9 16h7"/></>}
  {type==="release"&&<><circle cx="12" cy="12" r="9"/><path d="m7 12 3.5 3.5L17 9"/></>}
  {type==="progress"&&<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></>}
 </svg>;
}
export default function AssetSignals({value}: {value:OpsIndicator|undefined}){
 const v=value||empty;
 const total=v.stage_total;
 return <div className={styles.group} aria-label="Vehicle case indicators">
  {v.overdue>0&&<span className={`${styles.tag} ${styles.danger}`} title={`${v.overdue} overdue action(s)`}><Glyph type="task"/> {v.overdue} overdue</span>}
  {v.blockers>0&&<span className={`${styles.tag} ${styles.danger}`} title={`${v.blockers} active blockers`}><Glyph type="block"/> {v.blockers}</span>}
  {v.actions>0&&<span className={`${styles.tag} ${styles.pending}`} title={`${v.actions} open tasks`}><Glyph type="task"/> {v.actions}</span>}
  {v.documents>0&&<span className={`${styles.tag} ${v.documents===v.docs_verified?styles.success:styles.pending}`} title={`${v.docs_verified}/${v.documents} documents verified`}><Glyph type="doc"/> {v.docs_verified}/{v.documents}</span>}
  {v.release_ready&&<span className={`${styles.tag} ${styles.success}`} title="Release checklist complete"><Glyph type="release"/></span>}
  {total>0&&<div className={styles.progress} title={`${v.stage_done}/${total} workflow stages completed`} aria-label={`${v.stage_done} of ${total} stages complete`}>
     {Array.from({length:Math.min(12,total)},(_,i)=><span key={i} className={i<v.stage_done?styles.complete:undefined}/>)}
  </div>}
  {v.stage_current&&<span className={`${styles.tag} ${styles.pending}`} title={`Current stage: ${v.stage_current}`}><Glyph type="progress"/> {v.stage_current}</span>}
  {v.next_action&&<small className={styles.next} title={`${v.next_action.title} · ${v.next_action.owner} · ${v.next_action.due_at}`}>Next: {v.next_action.title}</small>}
 </div>;
}
