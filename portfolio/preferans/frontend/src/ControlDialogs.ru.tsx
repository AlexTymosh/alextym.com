"use client";

import { useEffect, useId, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import type { RoomView } from "./game-model.ru";
import { feedbackRemaining, TABLE_ZOOM_MIN, TABLE_ZOOM_MAX, TABLE_ZOOM_STEP } from "./control-feedback";
import styles from "./preferans-game.module.css";

export function UndoRequest({ busy, onCancel, onSend }: { busy: boolean; onCancel: () => void; onSend: (reason: string) => void }) {
  const [reason, setReason] = useState("Ошибся при выборе");
  const headingId = useId();
  const valid = reason.trim().length >= 5 && reason.trim().length <= 180 && !/[\r\n]/.test(reason);
  return <section className={`${styles.controlPanel} ${styles.undoDialog}`} role="dialog" aria-labelledby={headingId} onKeyDown={e=>{if(e.key==="Escape")onCancel();}}>
    <strong id={headingId}>Почему отменить последний ход или ставку?</strong>
    <form onSubmit={e=>{e.preventDefault();if(valid&&!busy)onSend(reason.trim());}}>
      <label>Причина<input className={styles.undoReason} type="text" value={reason} onChange={e=>setReason(e.target.value)} maxLength={180} required minLength={5}/></label>
      <p>Оба соперника должны согласиться на отмену.</p>
      <div className={styles.actions}>
        <button className={styles.primary} type="submit" disabled={busy||!valid}>Попросить прощения</button>
        <button type="button" onClick={onCancel}>Отмена</button>
      </div>
    </form>
  </section>;
}

function Notice({ message, at, serverNow }: { message: string; at: number; serverNow: () => number }) {
  const [visible, setVisible] = useState(()=>feedbackRemaining(at,serverNow())>0);
  useEffect(()=>{
    const timer=window.setTimeout(()=>setVisible(false),feedbackRemaining(at,serverNow()));
    return ()=>window.clearTimeout(timer);
  },[at,serverNow]);
  return visible?<div className={styles.feedbackNotice} role="status">{message}</div>:null;
}

/** Results arrive in the same authoritative room projection, not a second transport. */
export function ControlFeedback({ view, name, serverNow }: { view: RoomView; name: (seat: number) => string; serverNow: () => number }) {
  const undo=view.controls?.undo_result;
  const counter=view.controls?.counter_result;
  if(!undo&&!counter)return null;
  const undoMessage=undo?.outcome==="accepted"?"Тебя простили! Действие отменено.":undo?.outcome==="expired"?"Тебя не простили: время голосования истекло.":"Тебя не простили. Действие остаётся в силе.";
  return <div className={styles.feedbackStack}>
    {undo&&<Notice key={`${view.room_id}:undo:${undo.at_ms}:${undo.outcome}`} message={undoMessage} at={undo.at_ms} serverNow={serverNow}/>}
    {counter&&<Notice key={`${view.room_id}:counter:${counter.at_ms}:${counter.target}`} message={`${name(counter.target)}: записали ${counter.multiplier}х в гору за затягивание времени (${counter.penalty}).`} at={counter.at_ms} serverNow={serverNow}/>}
  </div>;
}

const subscribe=()=>()=>{};
const slotSnapshot=()=>document.getElementById("preferans-table-zoom-slot");
const serverSnapshot=()=>null;

export function TableZoom({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  const slot=useSyncExternalStore(subscribe,slotSnapshot,serverSnapshot);
  const toolbar=<span className={styles.zoomToolbar} role="group" aria-label="Масштаб игрового поля">
    <button type="button" title="Уменьшить игровое поле" aria-label="Уменьшить игровое поле" disabled={value<=TABLE_ZOOM_MIN} onClick={()=>onChange(value-TABLE_ZOOM_STEP)}>−</button>
    <button type="button" title="Исходный масштаб игрового поля" aria-label={`Исходный масштаб игрового поля (${value}%)`} onClick={()=>onChange(100)}>{value}%</button>
    <button type="button" title="Увеличить игровое поле" aria-label="Увеличить игровое поле" disabled={value>=TABLE_ZOOM_MAX} onClick={()=>onChange(value+TABLE_ZOOM_STEP)}>+</button>
  </span>;
  return slot?createPortal(toolbar,slot):toolbar;
}
