"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { blankLiveState, LiveMediaSession, type LiveState } from "./live-media-session";
import type { LiveFrame, LiveSender, MediaKind } from "./live-media-model";
import styles from "./preferans-live.module.css";

/** Room-level ownership; opening or closing a personal drawer cannot stop a call. */
export function useLiveMedia() {
  const engine = useRef<LiveMediaSession | null>(null);
  const [state,setState] = useState<LiveState>(blankLiveState);
  const [available,setAvailable] = useState(false);
  const bind = useCallback((seat:number, sender:LiveSender|null) => {
    engine.current?.dispose();engine.current=null;
    setState(blankLiveState());setAvailable(!!sender);
    if(sender)engine.current=new LiveMediaSession(seat,sender,setState);
  },[]);
  const receive = useCallback((frame:LiveFrame)=>engine.current?.receive(frame),[]);
  const leave = useCallback(()=>engine.current?.leave(),[]);
  const join = useCallback(()=>engine.current?.join(),[]);
  const toggle = useCallback((kind:MediaKind)=>{void engine.current?.toggle(kind);},[]);
  useEffect(()=>{
    const stop=()=>engine.current?.leave();
    window.addEventListener("pagehide",stop);
    window.addEventListener("offline",stop);
    return()=>{window.removeEventListener("pagehide",stop);window.removeEventListener("offline",stop);engine.current?.dispose();engine.current=null;};
  },[]);
  return {available,state,bind,receive,join,leave,toggle};
}
export type LiveMedia = ReturnType<typeof useLiveMedia>;

export function LiveMediaControls({media}: {media:LiveMedia}) {
  const s=media.state;
  return <section className={styles.panel} aria-label="Связь за столом">
    <h3>Связь за столом</h3>
    <p>Вход в звонок добровольный. При входе камера и микрофон выключены. В новой сцене нет функции записи. Звук и видео передаются напрямую между браузерами; IP-адрес может быть доступен собеседникам.</p>
    {!media.available ? <p role="status">Живая связь недоступна без активного WebSocket. Игра продолжает работать.</p> : <div className={styles.buttons}>
      {!s.joined && <button type="button" disabled={s.joining} onClick={media.join}>{s.joining?"Подключаем…":"Подключиться к звонку"}</button>}
      {(s.joined||s.joining)&&<button type="button" onClick={media.leave}>Выйти из звонка</button>}
      {s.joined&&<><button type="button" disabled={s.changing} aria-pressed={s.audio} onClick={()=>media.toggle("audio")}>{s.audio?"Выключить микрофон":"Включить микрофон"}</button>
      <button type="button" disabled={s.changing} aria-pressed={s.video} onClick={()=>media.toggle("video")}>{s.video?"Выключить камеру":"Включить камеру"}</button></>}
    </div>}
    {s.joined&&<p>Участников звонка: {s.roster.filter(Boolean).length} из 3. Для восстановления неудачного P2P-соединения выйди из звонка и подключись снова.</p>}
    {s.error&&<p role="alert">{s.error==="device"?"Устройство недоступно. Проверь разрешения браузера.":s.error==="peer"?"Прямое соединение не установлено. Некоторые сети требуют TURN, который не используется.":"Сигнализация недоступна. Подключись к звонку снова."}</p>}
    <p>После потери WebSocket камера и микрофон выключаются. Возвращение в звонок только вручную.</p>
  </section>;
}

export function MediaSeatTile({media,seat,own}:{media:LiveMedia;seat:number;own:boolean}) {
  const s=media.state;
  const member=s.roster[seat];
  const stream=s.streams[seat];
  const video=useRef<HTMLVideoElement>(null);
  const audio=useRef<HTMLAudioElement>(null);
  const [blocked,setBlocked]=useState(false);
  const showVideo=!!stream?.getVideoTracks().length&&!!(own?s.video:member?.video);
  const hear=!own&&!!stream?.getAudioTracks().length&&!!member?.audio;
  useEffect(()=>{
    const el=video.current;
    if(!el||!showVideo)return;
    el.srcObject=stream;void el.play().catch(()=>undefined);
    return()=>{el.srcObject=null;};
  },[stream,showVideo]);
  useEffect(()=>{
    const el=audio.current;
    if(!el||!hear)return;
    let active=true;el.srcObject=stream;
    void el.play().then(()=>{if(active)setBlocked(false);},()=>{if(active)setBlocked(true);});
    return()=>{active=false;el.srcObject=null;};
  },[stream,hear]);
  if(!s.joined||!member)return null;
  const status=s.connections[seat];
  return <div className={styles.tile} data-live-seat={seat} aria-label={`Связь: игрок ${seat+1}`}>
    {showVideo&&<video ref={video} autoPlay muted playsInline aria-label={`Камера игрока ${seat+1}`}/>}
    {hear&&<><audio ref={audio} autoPlay />{blocked&&<button type="button" onClick={()=>{void audio.current?.play().then(()=>setBlocked(false),()=>setBlocked(true));}}>Включить звук</button>}</>}
    <small>{(own?s.audio:member.audio)?"Микрофон включён":"Микрофон выключен"}{!own&&status&&status!=="connected"?" · связь не установлена":""}</small>
  </div>;
}
