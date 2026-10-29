"use client";

import { useState } from "react";
import Image from "next/image";
import fleetAvatar from "../assets/alex.webp";
import styles from "./message-card.module.css";

type Message = {
  id: number;
  author: string;
  kind: string;
  body: string;
  subject: string | null;
  recipient_email: string | null;
  ticket_id: string | null;
  direction: string | null;
  created_at: string;
};
const senderRole = (kind: string) => kind === "email" ? "EMAIL" : kind === "internal" ? "INTERNAL" : kind === "hoth" ? "HOTH" : "SYSTEM";
const messageDate = (value: string) => {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value.replace("T", " ").slice(0, 16) : d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

/** Read-only card: expansion affects presentation only, never message content or storage. */
export default function MessageCard({ event }: { event: Message }) {
  const [expanded, setExpanded] = useState(false);
  const author = event.author || "Fleet Hub";
  const isAlex = /^alex(?:\s+tym|$)/i.test(author);
  const isSystem = /fleet hub|workflow engine|system/i.test(author);
  const isWorkshop = /workshop|repair|garage|motor services|service centre|service center/i.test(author);
  const long = event.body.length > 190 || (event.body.match(/\n/g) || []).length > 2;
  const isEmail = event.kind === "email";
  const displayedSubject = event.subject?.replace(/^\[PR12 DEMO\]\s*/, "");
  return <article className={`${styles.card} ${isAlex ? styles.personal : ""} ${isSystem ? styles.system : ""}`}>
    <div className={styles.avatar} aria-label={author}>
      {isAlex ? <Image src={fleetAvatar} alt="Alex Tym" width={40} height={40} /> : isSystem ? <span className={styles.fleetLogo}>F</span> : isWorkshop ? <svg viewBox="0 0 24 24" width="21" height="21" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 6.2a4 4 0 0 0-5.2 5.1L3.8 16.8a2 2 0 0 0 2.9 2.8l5.5-5.5a4 4 0 0 0 5.1-5.2l-2.4 2.3-2.7-.7-.7-2.7z"/></svg> : isEmail ? <svg viewBox="0 0 24 24" width="21" height="21" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg> : <svg viewBox="0 0 24 24" width="21" height="21" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c.5-4.5 3.1-7 8-7s7.5 2.5 8 7"/></svg>}
    </div>
    <div className={styles.content}>
      <div className={styles.meta}><strong>{author}</strong><span className={styles.kind}>{senderRole(event.kind)}</span>{event.ticket_id&&<span className={styles.ticket}>{event.ticket_id}</span>}<time dateTime={event.created_at}>{messageDate(event.created_at)}</time></div>
      {displayedSubject&&<strong className={styles.subject}>{displayedSubject}</strong>}
      <p className={`${styles.body} ${long&&!expanded ? styles.collapsed : ""}`}>{event.body}</p>
      {event.recipient_email&&<div className={styles.recipient}>To: {event.recipient_email}{event.direction === "simulated_outgoing" ? " · Simulated email" : ""}</div>}
      {long&&<button className={styles.expand} type="button" aria-expanded={expanded} aria-label={`${expanded?"Collapse":"Expand"} message from ${author}`} onClick={()=>setExpanded(v=>!v)}>{expanded?"Show less ↑":"Read full message ↓"}</button>}
    </div>
  </article>;
}
