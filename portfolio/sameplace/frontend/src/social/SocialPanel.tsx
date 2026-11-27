"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { roomRequest } from "../rooms/client";
import type { RoomSummary } from "../rooms/client";
import { ROOM_ROOT } from "../room-transport";
import { t, command, failure, label } from "./helpers";
import { privacyKeys, type Social, type Privacy } from "./types";
import styles from "./social.module.css";

function ProfileForm({ data, submit, busy }: { data: Social; submit: (path: string, body: object) => Promise<void>; busy: boolean }) {
  const [nickname, setNickname] = useState(data.nickname); const [avatar, setAvatar] = useState(data.avatar);
  const [privacy, setPrivacy] = useState<Privacy>(data.privacy);
  return <form className={styles.form} onSubmit={e => { e.preventDefault(); void submit("social/profile", { nickname, avatar, privacy }); }}>
    <h3>{t("social.profile")}</h3><label>{t("social.nickname")}<input value={nickname} onChange={e=>setNickname(e.target.value)} required maxLength={40}/></label>
    <label>{t("social.avatar")}<select value={avatar} onChange={e=>setAvatar(e.target.value)}>{(["initials","circle","star","leaf"] as const).map(a=><option key={a} value={a}>{t(`avatar.${a}`)}</option>)}</select></label>
    <fieldset><legend>{t("social.privacy")}</legend>{privacyKeys.map(k=><label key={k} className={styles.check}><input type="checkbox" checked={privacy[k]} onChange={e=>setPrivacy(old=>({...old,[k]:e.target.checked}))}/>{t(`privacy.${k}`)}</label>)}</fieldset>
    <p>{t("social.privacy_note")}</p><button disabled={busy}>{t("room.save")}</button>
  </form>;
}
export function SocialPanel({ rooms, inboxRevision }: { rooms?: RoomSummary[]; inboxRevision?: number }) {
  const [open,setOpen] = useState(false), [data,setData] = useState<Social|null>(null), [error,setError] = useState(""), [target,setTarget] = useState(""), [busy,setBusy] = useState(false), [revision,setRevision] = useState(0);
  const running = useRef(false);
  useEffect(()=>{
    if (!open) return;
    const controller = new AbortController();
    void roomRequest<Social>("social/me", undefined, controller.signal).then(value=>{if(!controller.signal.aborted){setData(value);setError("");}}).catch(cause=>{if(!controller.signal.aborted){setData(null);setError(failure(cause));}});
    return ()=>controller.abort();
  },[open,revision,inboxRevision]);
  async function submit(path:string, body:object) {
    if(running.current) return; running.current=true;setBusy(true);setError("");
    try { await roomRequest(path,{...command(),...body});setRevision(n=>n+1); }
    catch(cause){setError(failure(cause));} finally{running.current=false;setBusy(false);}
  }
  return <section className={styles.panel}><button type="button" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{t("social.menu")}</button>
    {open && <><button onClick={()=>setRevision(n=>n+1)}>{t("room.refresh")}</button>{error&&<p role="alert">{error}</p>}
    {data&&<><p>{t("social.public_id")}: <code>{data.public_id}</code> <button onClick={()=>void navigator.clipboard.writeText(data.public_id).catch(()=>setError(t("error.UNAVAILABLE")))}>{t("room.copy")}</button></p>
    <ProfileForm key={JSON.stringify([data.nickname,data.avatar,data.privacy])} data={data} busy={busy} submit={submit}/>
    <h3>{t("social.friends")}</h3><form className={styles.form} onSubmit={e=>{e.preventDefault();void submit("social/friend",{target,action:"request"});}}><label>{t("social.friend_code")}<input required pattern="[a-f0-9]{32}" value={target} onChange={e=>setTarget(e.target.value)}/></label><button disabled={busy}>{t("social.request")}</button></form>
    <ul className={styles.list}>{data.friends.map(friend=><li key={friend.public_id}><strong>{label(friend.public_id,friend.nickname)}</strong> — {t(`friend.${friend.status}`)} {friend.status==="accepted"&&<span>{t(`presence.${friend.presence}`)}</span>}
    {friend.room&&<Link prefetch={false} href={`${ROOM_ROOT}/r/${friend.room.slug}`}>{friend.room.name}</Link>}{friend.last_seen_ms!==undefined&&<span>{t("social.last_seen",{date:new Date(friend.last_seen_ms).toLocaleString("ru")})}</span>}
    {(friend.status==="incoming"?["accept","decline","block"] as const:friend.status==="outgoing"?["cancel","block"] as const:friend.status==="accepted"?["remove","block"] as const:["unblock"] as const).map(action=><button key={action} disabled={busy} onClick={()=>void submit("social/friend",{target:friend.public_id,action})}>{t(`friend_action.${action}`)}</button>)}</li>)}</ul>
    {rooms&&(["favourites","recent"] as const).map(kind=><div key={kind}><h3>{t(`social.${kind}`)}</h3><ul>{data[kind].map(id=>rooms.find(r=>r.id===id)).filter((r):r is RoomSummary=>Boolean(r)).map(room=><li key={room.id}><Link prefetch={false} href={`${ROOM_ROOT}/r/${room.slug}`}>{room.name}</Link></li>)}</ul></div>)}
    <h3>{t("social.inbox")}</h3><ul className={styles.list}>{data.notices.map(n=><li key={n.id}><strong>{label(n.sender,n.nickname)}</strong> — {n.text} <Link prefetch={false} href={`${ROOM_ROOT}/r/${n.slug}`}>{t("social.join")}</Link> {!n.read&&<button disabled={busy} onClick={()=>void submit("social/read_notice",{notice_id:n.id})}>{t("social.read")}</button>}</li>)}</ul>{!data.notices.length&&<p>{t("social.no_notices")}</p>}
    </>}</>}
  </section>;
}
