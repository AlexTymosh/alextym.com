"use client";
import { useEffect, useRef, useState } from "react";
import { roomRequest, type Room } from "../rooms/client";
import { t, command, failure, label } from "./helpers";
import type { ChatPage, ChatMessage } from "./types";
import styles from "./social.module.css";

export function ChatPanel({ room, revision, online, me }: { room: Room; revision: string; online: boolean; me: string }) {
  const [page,setPage]=useState<ChatPage>({messages:[],before:null}), [older,setOlder]=useState<ChatMessage[]>([]), [cursor,setCursor]=useState<string|null>(null), [text,setText]=useState(""), [error,setError]=useState(""), [busy,setBusy]=useState(false), [reload,setReload]=useState(0);
  const running=useRef(false);
  const pageEpoch=useRef(0);
  useEffect(()=>{
    const controller=new AbortController();
    pageEpoch.current++;
    void roomRequest<ChatPage>(`rooms/${room.slug}/chat`,undefined,controller.signal).then(value=>{if(!controller.signal.aborted){setPage(value);setOlder([]);setCursor(value.before);setError("");}}).catch(cause=>{if(!controller.signal.aborted){setPage({messages:[],before:null});setOlder([]);setCursor(null);setError(failure(cause));}});
    return ()=>{controller.abort();pageEpoch.current++;};
  },[room.slug,revision,online,reload]);
  async function action(path:string,body:object) {
    if(running.current) return;running.current=true;setBusy(true);setError("");
    try{await roomRequest(`rooms/${room.slug}/chat/${path}`,{...(path==="cleanup"?{}:command()),...body});if(path==="send")setText("");if(path==="cleanup")setReload(n=>n+1);}catch(cause){setError(failure(cause));}finally{running.current=false;setBusy(false);}
  }
  async function loadOlder(){if(!cursor||running.current)return;running.current=true;setBusy(true);const epoch=pageEpoch.current;try{const result=await roomRequest<ChatPage>(`rooms/${room.slug}/chat/page`,{before:cursor});if(epoch===pageEpoch.current){setOlder(prev=>[...result.messages,...prev]);setCursor(result.before);}}catch(cause){setError(failure(cause));}finally{running.current=false;setBusy(false);}}
  return <section className={styles.panel}><h3>{t("chat.title")}</h3><button disabled={busy} onClick={()=>setReload(n=>n+1)}>{t("room.refresh")}</button>{error&&<p role="alert">{error}</p>}<p>{t("chat.retention")}</p>{cursor&&<button disabled={busy} onClick={()=>void loadOlder()}>{t("chat.older")}</button>}<ol className={styles.chat} aria-live="polite">{[...older,...page.messages].map(m=><li key={m.id}><div><strong>{label(m.sender,m.nickname)}</strong> <time dateTime={new Date(m.created_at_ms).toISOString()}>{new Date(m.created_at_ms).toLocaleString("ru")}</time></div><p>{m.text}</p>{online&&(m.sender===me||room.can_moderate)&&<button disabled={busy} onClick={()=>{const reason=m.sender===me?"":window.prompt(t("chat.reason"));if(reason!==null&&(m.sender===me||reason.trim()))void action("hide",{message_id:m.id,reason});}}>{t("chat.hide")}</button>}</li>)}</ol>
    {online?<form className={styles.form} onSubmit={e=>{e.preventDefault();void action("send",{text});}}><label>{t("chat.message")}<textarea value={text} onChange={e=>setText(e.target.value)} required maxLength={1000}/></label><button disabled={!online||busy||!text.trim()}>{t("chat.send")}</button></form>:<p>{t("chat.read_only")}</p>}
    {online&&room.can_moderate&&<button disabled={busy} onClick={()=>void action("cleanup",{})}>{t("chat.cleanup")}</button>}
  </section>;
}
