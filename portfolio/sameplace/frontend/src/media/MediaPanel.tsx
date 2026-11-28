"use client";
import {useCallback,useEffect,useRef,useState,type RefObject} from "react";
import {createTranslator} from "../i18n/messages";
import type {MediaProvider,MediaView} from "./types";
import type {AudioPreferences} from "./preferences";
import type {Person} from "../social/types";
import styles from "./media.module.css";
const t=createTranslator("ru");

export function VideoTile({stream}:{stream:MediaStream}){
  const ref=useRef<HTMLVideoElement>(null);
  useEffect(()=>{const node=ref.current;if(!node)return;node.srcObject=stream;return()=>{node.srcObject=null;};},[stream]);
  return <video className={styles.video} ref={ref} autoPlay playsInline muted aria-label={t("media.video")}/>;
}
function Voice({stream,volume,muted,output,onBlocked}:{stream:MediaStream;volume:number;muted:boolean;output:string;onBlocked:()=>void}){
  const ref=useRef<HTMLAudioElement>(null);
  useEffect(()=>{const node=ref.current;if(!node)return;node.srcObject=stream;void node.play().catch(onBlocked);return()=>{node.pause();node.srcObject=null;};},[stream,onBlocked]);
  useEffect(()=>{const node=ref.current;if(node){node.volume=volume/100;node.muted=muted;}},[volume,muted]);
  useEffect(()=>{const node=ref.current as (HTMLAudioElement&{setSinkId?:(id:string)=>Promise<void>})|null;if(node?.setSinkId)void node.setSinkId(output).catch(()=>undefined);},[output]);
  return <audio ref={ref} autoPlay muted={muted}/>;
}
type Props={provider:RefObject<MediaProvider|null>;view:MediaView;audio:AudioPreferences;updateAudio:(change:Partial<AudioPreferences>)=>void;people:Person[];canModerate:boolean;canChannel:boolean};
export function MediaPanel({provider,view,audio,updateAudio,people,canModerate,canChannel}:Props){
  const [devices,setDevices]=useState<MediaDeviceInfo[]>([]),[blocked,setBlocked]=useState(false);
  const sinks=useRef<HTMLDivElement>(null);
  const onBlocked=useCallback(()=>setBlocked(true),[]);
  const state=view.state;
  async function refreshDevices(){try{setDevices(await navigator.mediaDevices.enumerateDevices());}catch{setDevices([]);}}
  function retrySound(){setBlocked(false);for(const node of Array.from(sinks.current?.querySelectorAll("audio")??[]))void node.play().catch(onBlocked);}
  // Keep the audio sinks mounted independently of visible video tiles.
  return <section className={styles.panel} aria-label={t("media.title")}><h3>{t("media.title")}</h3>
    {!state?<p role="status">{t("media.disabled")}</p>:<><p role="status">{state.occupied?t("media.tab"):state.joined?t("media.joined"):t("media.ready")}</p><div className={styles.controls}>
    {state.joined?<><button type="button" onClick={()=>provider.current?.leave()}>{t("media.leave")}</button><button type="button" aria-pressed={view.microphone} disabled={state.muted} onClick={()=>void provider.current?.toggle("audio",audio.microphone)}>{t(view.microphone?"media.mic_off":"media.mic_on")}</button><button type="button" aria-pressed={view.camera} onClick={()=>void provider.current?.toggle("video",audio.camera)}>{t(view.camera?"media.cam_off":"media.cam_on")}</button></>:<button type="button" disabled={state.occupied} onClick={()=>provider.current?.join()}>{t("media.join")}</button>}
    {blocked&&<button type="button" onClick={retrySound}>{t("media.sound_retry")}</button>}</div>{state.muted&&<p role="alert">{t("media.muted")}</p>}
    <label>{t("media.channel")} <select value={state.mode} disabled={!canChannel} onChange={e=>provider.current?.mode(e.target.value==="location"?"location":"room")}><option value="room">{t("media.room")}</option><option value="location">{t("media.location")}</option></select></label>
    {view.status&&<p role="status">{t("media.problem")} ({view.status})</p>}
    <div ref={sinks}>{state.peers.map(peer=>view.remote[peer.id]&&<Voice key={peer.pair} stream={view.remote[peer.id]} volume={audio.voices} muted={audio.masterMute||peer.muted||!peer.microphone} output={audio.output} onBlocked={onBlocked}/>)}</div></>}
    <details><summary>{t("media.settings")}</summary><div className={styles.settings}>
      <label>{t("media.voices")} <input type="range" min="0" max="100" value={audio.voices} onChange={e=>updateAudio({voices:Number(e.target.value)})}/></label>
      <label>{t("decor.volume")} <input type="range" min="0" max="100" value={audio.music} onChange={e=>updateAudio({music:Number(e.target.value)})}/></label>
      <label><input type="checkbox" checked={audio.masterMute} onChange={e=>updateAudio({masterMute:e.target.checked})}/>{t("media.master_mute")}</label>
      <label><input type="checkbox" checked={audio.musicMute} onChange={e=>updateAudio({musicMute:e.target.checked})}/>{t("media.music_mute")}</label>
      <label><input type="checkbox" checked={audio.duck} onChange={e=>updateAudio({duck:e.target.checked})}/>{t("media.duck")}</label>
      <button type="button" onClick={()=>void refreshDevices()}>{t("media.devices")}</button>
      {(["microphone","camera"] as const).map(kind=><label key={kind}>{t(kind==="microphone"?"media.microphone":"media.camera")}<select disabled={kind==="microphone"?view.microphone:view.camera} value={audio[kind]} onChange={e=>updateAudio({[kind]:e.target.value})}><option value="">{t("media.default_device")}</option>{audio[kind]&&!devices.some(d=>d.deviceId===audio[kind])&&<option value={audio[kind]}>{t("media.saved_device")}</option>}{devices.filter(d=>d.kind===(kind==="microphone"?"audioinput":"videoinput")&&d.deviceId).map((d,i)=><option key={d.deviceId} value={d.deviceId}>{d.label||`${t("media.device")} ${i+1}`}</option>)}</select></label>)}
      {devices.some(d=>d.kind==="audiooutput"&&d.deviceId)&&<label>{t("media.output")}<select value={audio.output} onChange={e=>updateAudio({output:e.target.value})}><option value="">{t("media.default_device")}</option>{devices.filter(d=>d.kind==="audiooutput"&&d.deviceId).map((d,i)=><option key={d.deviceId} value={d.deviceId}>{d.label||`${t("media.device")} ${i+1}`}</option>)}</select></label>}
      <small>{t("media.echo_note")}</small>
    </div></details>
    <details><summary>{t("media.diagnostics")}</summary><p>RTT: {view.stats.rttMs??"—"} ms · {t("media.loss")}: {view.stats.loss} · {view.stats.inboundKbps} kbps</p>{state?.peers.map(peer=><div className={styles.controls} key={peer.id}><span>{people.find(p=>p.id===peer.id)?.nickname||t("media.participant")}: {view.connections[peer.id]||"—"}</span>{canModerate&&<button type="button" onClick={()=>provider.current?.moderate(peer.id,!peer.muted)}>{t(peer.muted?"media.restore_mic":"media.moderate_mic")}</button>}</div>)}</details>
  </section>;
}
