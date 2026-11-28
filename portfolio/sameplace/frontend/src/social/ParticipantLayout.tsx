"use client";
import type { ReactNode } from "react";
import type { MediaView } from "../media/types";
import { VideoTile } from "../media/MediaPanel";
import type { Person } from "./types";
import { t, label } from "./helpers";
import styles from "./social.module.css";
import { positions } from "./layout";

export function ParticipantLayout({ people, surface, backdrop, media }: { people: Person[]; surface?: string; backdrop?: ReactNode; media?: MediaView }) {
  const seated = people.filter(p => p.role !== "watch");
  const self = seated.find(p => p.self);
  const ordered = [...(self ? [self] : []), ...seated.filter(p=>!p.self)];
  const avatar = (p:Person) => {const stream=p.self?(media?.camera?media.local:null):media?.state?.peers.some(peer=>peer.id===p.id&&peer.camera)?media?.remote[p.id]:null;return <><span className={styles.mediaVisual}>{stream?<VideoTile stream={stream}/>:<span className={styles.avatar} aria-hidden="true">{p.avatar==="star"?"★":p.avatar==="leaf"?"♣":p.avatar==="circle"?"●":label(p.id,p.nickname).slice(0,2).toUpperCase()}</span>}</span><span>{label(p.id,p.nickname)}{p.self?` (${t("meeting.you")})`:""}</span><small>{t(`location.${p.location}`)}</small></>;};
  return <><div className={`${styles.tableLayout} ${backdrop?styles.scenicLayout:""}`} aria-label={t("meeting.participants")}>{backdrop?<div className={styles.backdrop}>{backdrop}</div>:<div className={`${styles.table} ${surface?.startsWith("mat")?styles.mat:surface?.startsWith("boat")?styles.deck:surface==="table_square"?styles.square:surface==="table_round"?styles.wood:""}`}>{t("meeting.surface")}</div>}{ordered.map((p,i)=><div className={styles.person} key={p.id} style={{gridArea:positions(ordered.length)[i]}}>{avatar(p)}</div>)}</div><div className={styles.observers}><strong>{t("meeting.observers")}</strong>{people.filter(p=>p.role==="watch").map(p=><div className={styles.person} key={p.id}>{avatar(p)}</div>)}</div></>;
}
