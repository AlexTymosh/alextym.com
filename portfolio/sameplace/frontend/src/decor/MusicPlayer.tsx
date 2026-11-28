"use client";
import {useEffect,useRef,useState} from "react";
import {demoWave,targetPosition} from "./audio";
import {musicGain,type AudioPreferences} from "../media/preferences";
import {name,t} from "./labels";
import {Stereo} from "./SceneCanvas";
import type {DecorView,Location,MusicAction,Scope} from "./types";
import styles from "./decor.module.css";

type Props={view:DecorView;location:Location;skin:string;online:boolean;busy:boolean;send:(scope:Scope,action:MusicAction,extra?:object)=>void;preferences:AudioPreferences;speaking:boolean;updateAudio:(change:Partial<AudioPreferences>)=>void};
export function MusicPlayer({view,location,skin,online,busy,send,preferences,speaking,updateAudio}:Props){
  const audio=useRef<HTMLAudioElement>(null),[allowed,setAllowed]=useState(false),[problem,setProblem]=useState(false),[scope,setScope]=useState<Scope>("room"),[expanded,setExpanded]=useState(false);
  const effective=view.music[location]??view.music.room,source=view.sources[effective.source_id],selected=view.music[scope]??view.music.room;
  const sourceId=source?.id,sourceUrl=source?.url,sourceMode=source?.mode,sourceAvailable=source?.available;
  const current=useRef({effective,source,offset:0,online,allowed});
  useEffect(()=>{current.current.offset=view.server_now_ms-Date.now();},[view.server_now_ms]);
  useEffect(()=>{current.current={...current.current,effective,source,online,allowed};},[effective,source,online,allowed]);
  useEffect(()=>{const node=audio.current;if(!node)return;let url:string|undefined;if(sourceAvailable&&sourceId){url=sourceMode==="recorded"?URL.createObjectURL(demoWave(sourceId)):sourceUrl;if(url)node.src=url;node.loop=sourceMode==="recorded";}return()=>{node.pause();node.removeAttribute("src");node.load();if(url?.startsWith("blob:"))URL.revokeObjectURL(url);};},[sourceId,sourceUrl,sourceMode,sourceAvailable]);
  const gain=musicGain(preferences,speaking);
  useEffect(()=>{const node=audio.current;if(node){node.volume=gain;node.muted=gain===0;}},[gain]);
  useEffect(()=>{const node=audio.current as (HTMLAudioElement&{setSinkId?:(id:string)=>Promise<void>})|null;if(node?.setSinkId)void node.setSinkId(preferences.output).catch(()=>undefined);},[preferences.output]);
  function synchronize(force=false){const node=audio.current,s=current.current;if(!node)return;if(!s.online||!s.allowed||s.effective.playback!=="playing"||!s.source?.available){node.pause();if(s.effective.playback==="stopped"&&node.readyState>0&&s.source?.mode==="recorded")node.currentTime=0;return;}if(s.source.mode==="recorded"&&node.readyState>0){const desired=targetPosition(s.effective,s.source,Date.now()+s.offset);if(force||Math.abs(desired-node.currentTime)>0.45)node.currentTime=desired;}if(node.paused)void node.play().then(()=>setProblem(false),()=>{current.current.allowed=false;setAllowed(false);setProblem(true);});}
  const syncRef=useRef(synchronize);useEffect(()=>{syncRef.current=synchronize;});
  useEffect(()=>{syncRef.current(true);},[effective.revision,effective.source_id,effective.playback,effective.position_ms,effective.started_at_ms,location,online,allowed]);
  useEffect(()=>{const timer=window.setInterval(()=>syncRef.current(),2000);return()=>window.clearInterval(timer);},[]);
  const allow=()=>{setAllowed(true);current.current.allowed=true;setProblem(false);syncRef.current(true);};
  return <section className={styles.panel}><h3>{t("decor.music")}</h3><button className={styles.device} type="button" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)} aria-label={t("decor.expand_device")}><svg viewBox="-65 -35 130 70" role="img" aria-label={name(skin)}><Stereo skin={skin}/></svg></button><audio ref={audio} preload="none" onLoadedMetadata={()=>syncRef.current(true)} onError={()=>{current.current.allowed=false;setAllowed(false);setProblem(true);}}/><p role="status">{name(effective.source_id)} · {name(effective.playback)} {view.music[location]?name(location):name("room")}</p>{!allowed||problem?<button type="button" onClick={allow}>{t("decor.enable_audio")}</button>:null}{problem&&<p role="alert">{t("decor.audio_problem")}</p>}<label>{t("decor.volume")} <input type="range" min="0" max="100" value={preferences.music} onChange={e=>updateAudio({music:Number(e.target.value)})}/></label><label><input type="checkbox" checked={preferences.musicMute} onChange={e=>updateAudio({musicMute:e.target.checked})}/>{t("decor.mute")}</label>{expanded&&view.can_dj&&<div className={styles.controls}><label>{t("decor.scope")}<select value={scope} onChange={e=>setScope(e.target.value as Scope)}>{(["room","lounge","table"] as Scope[]).map(x=><option key={x} value={x}>{name(x)}</option>)}</select></label><label>{t("decor.source")}<select disabled={busy} value={selected.source_id} onChange={e=>send(scope,"select",{source_id:e.target.value})}>{Object.values(view.sources).map(s=><option key={s.id} value={s.id} disabled={!s.available}>{name(s.id)}{s.available?"":` — ${t("decor.unavailable")}`}</option>)}</select></label>{(["play","pause","stop"] as MusicAction[]).map(action=><button key={action} disabled={busy} onClick={()=>send(scope,action)}>{name(action)}</button>)}{view.sources[selected.source_id]?.mode==="recorded"&&<button disabled={busy} onClick={()=>send(scope,"seek",{position_ms:0})}>{t("decor.rewind")}</button>}{scope!=="room"&&<button disabled={busy} onClick={()=>send(scope,"inherit")}>{t("decor.inherit")}</button>}</div>}<small>{t("decor.radio_note")}</small></section>;
}
