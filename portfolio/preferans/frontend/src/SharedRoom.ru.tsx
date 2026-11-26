"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CardArtwork } from "./CardArtwork.ru";
import { type RoomView, suitSymbol } from "./game-model.ru";
import { type SeatProfile } from "./table-model";
import { Notebook } from "./Notebook.ru";
import { VesnaRadio } from "./VesnaRadio.ru";
import { musicPosition, TRACKS, type Music, type OverlayKind, type SharedAction } from "./presentation-model";
import styles from "./preferans-shared.module.css";

export type SharedCommand=(action:SharedAction,args?:Record<string,unknown>)=>void;
const labels:Record<OverlayKind,string>={score_sheet:"Пулька",radio:"Магнитофон",last_trick:"Последняя взятка",widow_replay:"Прикуп",discard_replay:"Просмотр сноса"};
const names=(seat:number,profiles:SeatProfile[]|null)=>profiles?.[seat]?.name||`Игрок ${seat+1}`;
function RadioArt(){return <VesnaRadio className={styles.radioArt}/>;}
export function SharedObjects({busy,open}:{busy:boolean;open:(kind:OverlayKind)=>void}){
  return <div className={styles.objects}>
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
export function SharedRoom({view,profiles,busy,command,serverNow,sheetExit,scoreAdjustment}:{view:RoomView;profiles:SeatProfile[]|null;busy:boolean;command:SharedCommand;serverNow:()=>number;sheetExit?:ReactNode;scoreAdjustment?:ReactNode}){
  const p=view.presentation!;const radio=useRadio(p.music,serverNow,p.enabled);
  const close=()=>p.overlay&&command("overlay_close",{overlay_id:p.overlay.id});
  const my=view.my_seat;
  return <section className={styles.shared} aria-label="Общее пространство">
    <audio ref={radio.audio} preload="none" onError={()=>radio.setFailed(true)}/>
    {p.enabled&&(p.music.playing||radio.blocked)&&radio.needsGesture&&<button type="button" onClick={radio.unlock}>Включить звук на моём устройстве</button>}
    {radio.failed&&<p role="status">Аудиофайл недоступен. Игра продолжается.</p>}
    {p.enabled&&!p.break&&<button className={styles.breakButton} type="button" disabled={busy||view.claim?.status==="pending"} onClick={()=>command("break_start")}>Перерыв</button>}
    {p.break&&<div className={styles.breakPanel} role="status"><strong>Общий перерыв · готовность {p.break.ready.filter(Boolean).length}/3</strong>
      <p>{p.break.ready.map((v,i)=>`${names(i,profiles)}: ${v?"готов":"ожидает"}`).join(" · ")}</p>
      {my!==null&&<button type="button" disabled={busy||!p.enabled} onClick={()=>command("break_ready",{break_id:p.break!.id,ready:!p.break!.ready[my]})}>{p.break.ready[my]?"Отозвать готовность":"Готов продолжить"}</button>}
    </div>}
    {p.overlay&&<section className={`${styles.panel} ${p.overlay.kind==="score_sheet"?styles.scoreOverlay:p.overlay.kind==="last_trick"?styles.lastTrickOverlay:p.overlay.kind==="radio"?styles.radioOverlay:""}`} role={p.overlay.kind==="score_sheet"||p.overlay.kind==="last_trick"||p.overlay.kind==="radio"?"dialog":undefined} aria-label={labels[p.overlay.kind]} data-shared-overlay={p.overlay.kind}>
      {p.overlay.kind!=="score_sheet"&&<header><div><strong>{p.overlay.kind==="last_trick"?`${names(p.overlay.seat,profiles)} смотрит последнюю взятку`:labels[p.overlay.kind]}</strong><small>Открыл: {names(p.overlay.seat,profiles)}. {p.overlay.kind==="discard_replay"?"Карты видит только заказчик.":"Видят все игроки."}</small></div><button type="button" disabled={busy} onClick={close}>Закрыть</button></header>}
      {p.overlay.kind==="score_sheet"&&<Notebook view={view} profiles={profiles} title={`${names(p.overlay.seat,profiles)} смотрит листик`} sheetExit={sheetExit} scoreAdjustment={scoreAdjustment} onClose={close} closeDisabled={busy}/>}
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
