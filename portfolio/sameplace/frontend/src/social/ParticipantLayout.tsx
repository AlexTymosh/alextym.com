"use client";
import type { Person } from "./types";
import { t, label } from "./helpers";
import styles from "./social.module.css";
import { positions } from "./layout";

export function ParticipantLayout({ people }: { people: Person[] }) {
  const seated = people.filter(p => p.role !== "watch");
  const self = seated.find(p => p.self);
  const ordered = [...(self ? [self] : []), ...seated.filter(p=>!p.self)];
  const avatar = (p:Person) => <><span className={styles.avatar} aria-hidden="true">{p.avatar==="star"?"★":p.avatar==="leaf"?"♣":p.avatar==="circle"?"●":label(p.id,p.nickname).slice(0,2).toUpperCase()}</span><span>{label(p.id,p.nickname)}{p.self?` (${t("meeting.you")})`:""}</span><small>{t(`location.${p.location}`)}</small></>;
  return <><div className={styles.tableLayout} aria-label={t("meeting.participants")}><div className={styles.table}>{t("meeting.surface")}</div>{ordered.map((p,i)=><div className={styles.person} key={p.id} style={{gridArea:positions(ordered.length)[i]}}>{avatar(p)}</div>)}</div><div className={styles.observers}><strong>{t("meeting.observers")}</strong>{people.filter(p=>p.role==="watch").map(p=><div className={styles.person} key={p.id}>{avatar(p)}</div>)}</div></>;
}
