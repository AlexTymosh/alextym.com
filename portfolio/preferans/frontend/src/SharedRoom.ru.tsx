"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CardArtwork } from "./CardArtwork.ru";
import { type RoomView, suitSymbol } from "./game-model.ru";
import { type SeatProfile } from "./table-model";
import { Notebook } from "./Notebook.ru";
import { musicPosition, TRACKS, type Music, type OverlayKind, type SharedAction } from "./presentation-model";
import styles from "./preferans-shared.module.css";

export type SharedCommand=(action:SharedAction,args?:Record<string,unknown>)=>void;
const labels:Record<OverlayKind,string>={score_sheet:"Пулька",radio:"Магнитофон",last_trick:"Последняя взятка",widow_replay:"Прикуп",discard_replay:"Просмотр сноса"};
const names=(seat:number,profiles:SeatProfile[]|null)=>profiles?.[seat]?.name||`Игрок ${seat+1}`;
function RadioArt(){return <svg viewBox="0 0 300 142" aria-hidden="true" className={styles.radioArt}>
  <rect x="95" y="4" width="110" height="22" rx="7" fill="none" stroke="#b6b4a7" strokeWidth="8"/>
  <rect x="3" y="24" width="294" height="114" rx="8" fill="#30332e" stroke="#c7c0aa" strokeWidth="3"/>
  <rect x="12" y="31" width="276" height="23" rx="3" fill="#aeaa97"/>
  <rect x="19" y="35" width="185" height="14" fill="#2f3932"/>
  {Array.from({length:20},(_,i)=><path key={i} d={`M${24+i*9} 36v${i%5===0?11:6}`} stroke="#e3c479"/>)}
  <circle cx="265" cy="42" r="10" fill="#3a3b34" stroke="#ded5be"/>
  {[53,247].map(x=><g key={x}><circle cx={x} cy="95" r="36" fill="#141a16" stroke="#8c8d7e" strokeWidth="3"/>{[8,15,22,29].map(r=><circle key={r} cx={x} cy="95" r={r} fill="none" stroke="#454942" strokeWidth="2"/>)}</g>)}
  <rect x="99" y="61" width="102" height="66" rx="4" fill="#bdb6a3"/>
  <rect x="108" y="71" width="84" height="37" rx="3" fill="#454a41"/>
  {[125,175].map(x=><circle key={x} cx={x} cy="89" r="12" fill="#d7cdb6" stroke="#6b6c60" strokeWidth="5"/>)}
  <rect x="134" y="84" width="32" height="11" fill="#191f19"/>
  <text x="150" y="121" fill="#252c25" textAnchor="middle" fontSize="10" fontWeight="bold">STEREO</text>
</svg>}
export function SharedObjects({view,busy,open}:{view:RoomView;busy:boolean;open:(kind:OverlayKind)=>void}){
  return <div className={styles.objects}>
    <button type="button" className={styles.paperButton} disabled={busy||!view.score} onClick={()=>open("score_sheet")} aria-label="Открыть общую пульку"><span aria-hidden="true">╲ │ ╱<br/>──○──<br/> ╱ │ ╲</span>Пулька</button>
    <button type="button" className={styles.radioButton} disabled={busy} onClick={()=>open("radio")} aria-label="Открыть магнитофон"><RadioArt/></button>
  </div>;
}
function useRadio(music:Music,serverNow:()=>number,enabled:boolean){
  const audio=useRef<HTMLAudioElement>(null);
  const permitted=useRef(false);
  const [blocked,setBlocked]=useState(false);
  const [unlocked,setUnlocked]=useState(false);
  const [failed,setFailed]=useState(false);
  const [volume,setVolume]=useState(.35);
  const [muted,setMuted]=useState(false);
  const [display,setDisplay]=useState({track:music.track,offset:music.offset_ms});
  const sync=()=>{
    const el=audio.current;if(!el)return;
    const pos=musicPosition(music,serverNow());setDisplay(pos);
    if(!enabled||!music.playing||!permitted.current){el.pause();return;}
    const url=TRACKS[pos.track];
    if(el.getAttribute("src")!==url)el.src=url;
    if(el.readyState>=1&&Math.abs(el.currentTime-pos.offset/1000)>.8)el.currentTime=pos.offset/1000;
    el.volume=volume;el.muted=muted;
    if(el.paused)void el.play().then(()=>setBlocked(false)).catch(()=>{permitted.current=false;setUnlocked(false);setBlocked(true);});
  };
  // All audio is local. No playback position is sent to the server.
  useEffect(()=>{sync();if(!enabled||!music.playing)return;const interval=setInterval(sync,1000);return()=>clearInterval(interval);},[music,serverNow,enabled,volume,muted]); // eslint-disable-line react-hooks/exhaustive-deps
  const unlock=()=>{
    const el=audio.current;if(!el||!enabled)return;
    permitted.current=true;setUnlocked(true);setBlocked(false);setFailed(false);
    const pos=musicPosition(music,serverNow());
    if(el.getAttribute("src")!==TRACKS[pos.track])el.src=TRACKS[pos.track];
    el.volume=volume;el.muted=muted;
    // Invoke play in the real user gesture, then pause if the shared state is stopped.
    // Reconciliation will start it again after the shared play command commits.
    void el.play().then(()=>{if(!music.playing)el.pause();}).catch(()=>{permitted.current=false;setUnlocked(false);setBlocked(true);});
  };
  return {audio,display,volume,setVolume,muted,setMuted,blocked,unlock,needsGesture:!unlocked,failed,setFailed};
}
export function SharedRoom({view,profiles,busy,command,serverNow,scoreTable}:{view:RoomView;profiles:SeatProfile[]|null;busy:boolean;command:SharedCommand;serverNow:()=>number;scoreTable:ReactNode}){
  const p=view.presentation!;const radio=useRadio(p.music,serverNow,p.enabled);
  const close=()=>p.overlay&&command("overlay_close",{overlay_id:p.overlay.id});
  const my=view.my_seat;
  return <section className={styles.shared} aria-label="Общее пространство">
    <audio ref={radio.audio} preload="none" onError={()=>radio.setFailed(true)}/>
    {p.enabled&&(p.music.playing||radio.blocked)&&radio.needsGesture&&<button type="button" onClick={radio.unlock}>Включить звук на моём устройстве</button>}
    {radio.failed&&<p role="status">Аудиофайл недоступен. Игра продолжается.</p>}
    {p.enabled&&!p.break&&<button type="button" disabled={busy} onClick={()=>command("break_start")}>Перерыв</button>}
    {p.break&&<div className={styles.breakPanel} role="status"><strong>Общий перерыв · готовность {p.break.ready.filter(Boolean).length}/3</strong>
      <p>{p.break.ready.map((v,i)=>`${names(i,profiles)}: ${v?"готов":"ожидает"}`).join(" · ")}</p>
      {my!==null&&<button type="button" disabled={busy||!p.enabled} onClick={()=>command("break_ready",{break_id:p.break!.id,ready:!p.break!.ready[my]})}>{p.break.ready[my]?"Отозвать готовность":"Готов продолжить"}</button>}
    </div>}
    {p.overlay&&<section className={`${styles.panel} ${p.overlay.kind==="score_sheet"?styles.scoreOverlay:""}`} role={p.overlay.kind==="score_sheet"?"dialog":undefined} aria-label={labels[p.overlay.kind]} data-shared-overlay={p.overlay.kind}>
      <header><div><strong>{labels[p.overlay.kind]}</strong><small>Открыл: {names(p.overlay.seat,profiles)}. {p.overlay.kind==="discard_replay"?"Карты видит только заказчик.":"Видят все игроки."}</small></div><button type="button" disabled={busy} onClick={close}>Закрыть</button></header>
      {p.overlay.kind==="score_sheet"&&<><Notebook view={view} profiles={profiles}/><details><summary>Таблица расчётов</summary>{scoreTable}</details></>}
      {p.overlay.kind==="last_trick"&&<><div className={styles.replay}>{(view.last_trick??[]).map(play=><div key={play.owner}><span>{names(play.owner,profiles)}</span><CardArtwork card={play.card}/></div>)}</div><p>Победитель: {names(view.last_trick_winner??0,profiles)}{view.last_trick_suit?` · Масть ${suitSymbol(view.last_trick_suit)}`:""}. Следующий разрешённый ход закроет просмотр.</p></>}
      {p.overlay.kind==="widow_replay"&&<div className={styles.replay}>{(view.widow??[]).map((card,i)=><div key={i}><CardArtwork card={card}/></div>)}</div>}
      {p.overlay.kind==="discard_replay"&&<div className={styles.replay}>{view.my_seat===view.declarer&&view.my_seat===p.overlay.seat ? (view.own_discard??[]).map((card,i)=><div key={i}><CardArtwork card={card}/></div>) : <p>{names(p.overlay.seat,profiles)} смотрит свои сброшенные карты.</p>}</div>}
      {p.overlay.kind==="radio"&&<div className={styles.radio}><RadioArt/><p>Тестовая мелодия {radio.display.track+1} · {Math.floor(radio.display.offset/1000)} с / 12 с</p><p>Пока только собственные тестовые звуки; коммерческие записи не включены.</p>
        <div className={styles.buttons}>{([['previous','⏮','Предыдущая'],['play','▶','Играть'],['pause','Ⅱ','Пауза музыки'],['stop','■','Стоп'],['next','⏭','Следующая']] as const).map(([action,icon,label])=><button key={action} type="button" aria-label={label} disabled={busy||!p.enabled} onClick={()=>{if(action==='play')radio.unlock();command('music',{command:action});}}>{icon}</button>)}</div>
        <label>Моя громкость <input type="range" min={0} max={1} step={.05} value={radio.volume} onChange={e=>radio.setVolume(Number(e.target.value))}/></label><label><input type="checkbox" checked={radio.muted} onChange={e=>radio.setMuted(e.target.checked)}/> Без звука</label>
        {radio.blocked&&<p>Браузер заблокировал звук. Нажми «Включить звук».</p>}
      </div>}
    </section>}
  </section>;
}
