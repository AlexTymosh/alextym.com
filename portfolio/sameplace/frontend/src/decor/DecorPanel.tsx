"use client";
import {useEffect,useRef,useState} from "react";
import {roomRequest,RoomRequestError,type Room} from "../rooms/client";
import {ParticipantLayout} from "../social/ParticipantLayout";
import type {Snapshot} from "../social/types";
import {SceneCanvas} from "./SceneCanvas";
import {SceneEditor} from "./SceneEditor";
import {MusicPlayer} from "./MusicPlayer";
import {name,t} from "./labels";
import type {DecorView,Location,MusicAction,Scope} from "./types";
import styles from "./decor.module.css";

export function DecorPanel({room,snapshot,online,onDenied}:{room:Room;snapshot:Snapshot|null;online:boolean;onDenied:()=>void}){
  const [view,setView]=useState<DecorView|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[refresh,setRefresh]=useState(0),[editing,setEditing]=useState<Location|null>(null),[hide,setHide]=useState(false),[contrast,setContrast]=useState(false),[zoom,setZoom]=useState(100);
  const revision=snapshot?.room_revision,meeting=snapshot?.meeting_id,location=snapshot?.people.find(p=>p.self)?.location??"lounge";
  const denied=useRef(onDenied);useEffect(()=>{denied.current=onDenied;},[onDenied]);
  const serial=useRef(0),active=useRef(true);useEffect(()=>{active.current=true;return()=>{active.current=false;serial.current++;};},[]);
  function showError(cause:unknown){if(cause instanceof RoomRequestError){if([401,403,404].includes(cause.status)){if(cause.status!==403||cause.code==="ROOM_NOT_FOUND"){setView(null);denied.current();return;}}if(["SCENE_CONFLICT","MUSIC_CONFLICT","SOURCE_UNAVAILABLE","TEMPLATE_LIMIT"].includes(cause.code)){setError(name(cause.code));return;}}setError(t("decor.error"));}
  const errorRef=useRef(showError);useEffect(()=>{errorRef.current=showError;});
  useEffect(()=>{const abort=new AbortController(),token=++serial.current;void roomRequest<DecorView>(`rooms/${room.slug}/decor`,undefined,abort.signal).then(data=>{if(!abort.signal.aborted&&token===serial.current&&data.id===room.id){setView(data);setError("");}},cause=>{if(!abort.signal.aborted&&token===serial.current){if(cause instanceof RoomRequestError&&[401,403,404].includes(cause.status)){setView(null);denied.current();}else errorRef.current(cause);}});return()=>abort.abort();},[room.slug,room.id,room.version,revision,meeting,refresh]);
  async function send(action:string,payload:object){if(busy)return false;setBusy(true);setError("");const token=++serial.current;try{const data=await roomRequest<DecorView>(`rooms/${room.slug}/decor/${action}`,{request_id:crypto.randomUUID(),...payload});if(active.current&&data.id===room.id){if(token===serial.current)setView(data);else setRefresh(v=>v+1);}return true;}catch(cause){if(active.current){showError(cause);if(cause instanceof RoomRequestError&&cause.status===409)setRefresh(v=>v+1);}return false;}finally{if(active.current)setBusy(false);}}
  function music(scope:Scope,action:MusicAction,extra:object={}){if(view)void send("music",{scope,action,revision:view.music_versions[scope]??0,...extra});}
  if(!view)return <section className={styles.panel}>{error?<p role="alert">{error}</p>:<p role="status">{t("decor.loading")}</p>}<button onClick={()=>setRefresh(v=>v+1)}>{t("decor.refresh")}</button>{snapshot&&<ParticipantLayout people={snapshot.people}/>}</section>;
  const scene=view.scenes[location].scene;
  return <div className={styles.workspace}><section className={styles.panel}><h3>{name(scene.background)} · {name(location)}</h3><div className={styles.previewViewport}><div style={{width:`${zoom}%`,filter:contrast?"contrast(1.35)":undefined}}>{snapshot?<ParticipantLayout people={snapshot.people.filter(p=>p.location===location)} surface={scene.surface} backdrop={<SceneCanvas scene={scene} hide={hide}/>}/>:<SceneCanvas scene={scene} hide={hide}/>}</div></div><div className={styles.controls}><label><input type="checkbox" checked={hide} onChange={e=>setHide(e.target.checked)}/>{t("decor.hide")}</label><label><input type="checkbox" checked={contrast} onChange={e=>setContrast(e.target.checked)}/>{t("decor.contrast")}</label><label>{t("decor.zoom")}<input type="range" min="75" max="150" value={zoom} onChange={e=>setZoom(Number(e.target.value))}/></label><button onClick={()=>setRefresh(v=>v+1)}>{t("decor.refresh")}</button>{view.can_design&&<><button disabled={editing!==null} onClick={()=>setEditing("lounge")}>{t("decor.edit_lounge")}</button><button disabled={editing!==null} onClick={()=>setEditing("table")}>{t("decor.edit_table")}</button></>}</div>{error&&<p role="alert">{error}</p>}</section>{editing&&view.can_design&&<SceneEditor key={editing} location={editing} view={view} busy={busy} send={send} close={()=>setEditing(null)}/>}<MusicPlayer view={view} location={location} skin={scene.skin} online={online} busy={busy} send={music}/></div>;
}
