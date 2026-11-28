"use client";
import { useEffect, useRef, useState } from "react";
import { roomRequest, type Room } from "../rooms/client";
import { openMeeting, type ConnectionStatus } from "./realtime";
import { SocialPanel } from "./SocialPanel";
import { DecorPanel } from "../decor/DecorPanel";
import { ChatPanel } from "./ChatPanel";
import { CallFriends } from "./CallFriends";
import { Locations } from "./Locations";
import { t, command, failure } from "./helpers";
import type { Snapshot } from "./types";
import styles from "./social.module.css";

export function MeetingPanel({room,onDenied,onRoomChange}:{room:Room;onDenied:()=>void;onRoomChange:()=>Promise<void>}) {
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null),[status,setStatus]=useState<ConnectionStatus>("connecting"),[code,setCode]=useState(""),[generation,setGeneration]=useState(0),[favourite,setFavourite]=useState(""),[showHistory,setShowHistory]=useState(false);
  const callbacks=useRef({onDenied,onRoomChange});useEffect(()=>{callbacks.current={onDenied,onRoomChange};},[onDenied,onRoomChange]);
  useEffect(()=>{let lastMeeting="",lastRoom=-1;return openMeeting(room.slug,room.id,{snapshot:value=>{if(lastRoom!==-1&&(lastMeeting!==value.meeting_id||lastRoom!==value.room_revision))void callbacks.current.onRoomChange();lastMeeting=value.meeting_id;lastRoom=value.room_revision;setSnapshot(value);},status:(value,reason)=>{setStatus(value);setCode(reason??"");if(value!=="online")setSnapshot(null);},denied:()=>{setSnapshot(null);callbacks.current.onDenied();}});},[room.slug,room.id,generation]);
  const me=snapshot?.people.find(p=>p.self);
  async function setFav(enabled:boolean){try{await roomRequest(`rooms/${room.slug}/favourite`,{...command(),enabled});setFavourite(t(enabled?"social.favourite_added":"social.favourite_removed"));}catch(cause){setFavourite(failure(cause));}}
  return <div className={styles.shell}><section className={styles.panel}><h2>{t("meeting.title")}</h2><p role="status">{t(`connection.${status}`)} {code==="WAIT_CAPACITY"&&t("error.WAIT_CAPACITY")}{code==="OTHER_MEETING"&&t("error.OTHER_MEETING")}{code==="TAB_LIMIT"&&t("error.TAB_LIMIT")}</p>{status!=="online"&&<button onClick={()=>setGeneration(v=>v+1)}>{t("meeting.retry")}</button>}<button onClick={()=>void setFav(true)}>{t("social.add_favourite")}</button><button onClick={()=>void setFav(false)}>{t("social.remove_favourite")}</button>{favourite&&<p role="status">{favourite}</p>}
    <DecorPanel room={room} snapshot={snapshot} online={status==="online"} onDenied={onDenied}/></section><CallFriends room={room} online={status==="online"} people={snapshot?.people??[]}/><SocialPanel inboxRevision={snapshot?.inbox_revision}/>{status!=="online"&&<section className={styles.panel}><button aria-expanded={showHistory} onClick={()=>setShowHistory(v=>!v)}>{t("chat.history")}</button>{showHistory&&<ChatPanel key="history" room={room} revision="manual" online={false} me=""/>}</section>}{snapshot&&status==="online"&&me&&<><Locations room={room} snapshot={snapshot}/><ChatPanel key="live" room={room} revision={`${snapshot.meeting_id}:${snapshot.chat_revision}`} online={true} me={me.id}/></>}
  </div>;
}
