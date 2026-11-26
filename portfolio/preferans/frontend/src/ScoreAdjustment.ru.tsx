"use client";

import { useState } from "react";
import type { RoomView } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
import styles from "./preferans-game.module.css";

type AdjustRequest = {field:"pool"|"hill"|"vist";seat:number;against:number|null;delta:number;reason:string};

export function ScoreAdjustment({view,profiles,busy,adjust}:{view:RoomView;profiles:SeatProfile[]|null;busy:boolean;adjust:(request:AdjustRequest)=>void}) {
  const [selectedField,setSelectedField]=useState<AdjustRequest["field"]>("hill");
  const [seat,setSeat]=useState(0);
  const [against,setAgainst]=useState(1);
  const [deltaText,setDeltaText]=useState("1");
  const [reason,setReason]=useState("");
  const field=view.final_review&&selectedField==="pool"?"hill":selectedField;
  const names=[0,1,2].map(i=>profiles?.[i]?.name||`Игрок ${i+1}`);
  if(!view.room_admin||!view.score||!(["playing","between","awaiting_settlement"] as string[]).includes(view.status))return null;
  const delta=Number(deltaText);
  const before=field==="vist"?view.score.vists[seat][against]:view.score[field][seat];
  const after=before+delta;
  const valid=Number.isSafeInteger(delta)&&delta!==0&&Math.abs(delta)<=1000&&after>=0&&reason.trim().length>=5&&reason.trim().length<=180&&
    (field!=="vist"||seat!==against)&&(field!=="pool"||(!view.final_review&&after<=(view.score.target??20)&&!view.score.pool.every((v,i)=>(i===seat?after:v)===(view.score?.target??20))));
  return <details className={styles.adjustments}>
    <summary>Корректировка расчётов</summary>
    <p>Можно исправлять записи многократно до подтверждения итогов. Каждое исправление сохраняется в журнале.</p>
    <div className={styles.adjustGrid}>
      <label>Запись <select value={field} onChange={e=>setSelectedField(e.target.value as AdjustRequest["field"])}>
        <option value="hill">Гора</option><option value="pool" disabled={!!view.final_review}>Пуля</option><option value="vist">Висты</option>
      </select></label>
      <label>Игрок <select value={seat} onChange={e=>setSeat(Number(e.target.value))}>{names.map((name,i)=><option key={i} value={i}>{name}</option>)}</select></label>
      {field==="vist"&&<label>На кого <select value={against} onChange={e=>setAgainst(Number(e.target.value))}>{names.map((name,i)=><option key={i} value={i} disabled={i===seat}>{name}</option>)}</select></label>}
      <label>Изменение (+ или −) <input type="number" step="1" min="-1000" max="1000" value={deltaText} onChange={e=>setDeltaText(e.target.value)}/></label>
      <label>Причина <input maxLength={180} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Почему изменён расчёт"/></label>
    </div>
    <p aria-live="polite">Предпросмотр: {before} → {after}</p>
    <button type="button" className={styles.confirmAdjustment} disabled={busy||view.claim?.status==="pending"||!valid} onClick={()=>{
      if(valid&&window.confirm(`Записать корректировку: ${before} → ${after}?`))adjust({field,seat,against:field==="vist"?against:null,delta,reason:reason.trim()});
    }}>Подтвердить корректировку</button>
    {!!view.controls?.adjustments.length&&<details><summary>Журнал последних корректировок</summary><ol>{view.controls.adjustments.map((entry,index)=><li key={`${entry.game_version}-${index}`}>{names[entry.seat]}{entry.against!==null?` → ${names[entry.against]}`:""}: {entry.before} → {entry.after}. {entry.reason}</li>)}</ol></details>}
  </details>;
}
