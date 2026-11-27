"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { createTranslator, type MessageKey } from "../i18n/messages";
import { ROOM_ROOT } from "../room-transport";
import { roomRequest, RoomRequestError, INTERIORS, ROLES, type Room, type Identity, type Catalogue, type Limits, type Interior, type Role } from "./client";
import styles from "./rooms.module.css";

const t = createTranslator("ru");
export type Authenticate = (mode: "login" | "register" | "google", email: string, password: string) => Promise<"signed-in" | "verify-email">;
type Props = { slug?: string; token?: string; authenticate: Authenticate; signOut: () => Promise<void> };
const errorKeys = new Set<MessageKey>(["error.AUTH_REQUIRED", "error.ACCESS_DENIED", "error.ROOM_NOT_FOUND", "error.INVITE_INVALID", "error.OWNER_LIMIT", "error.SLUG_TAKEN", "error.STALE_VERSION", "error.CAPACITY_LIMIT", "error.STORAGE_LIMIT", "error.MEMBERSHIP_LIMIT", "error.INVITE_LIMIT", "error.CREATOR_REQUIRED", "error.TRANSFER_INVALID", "error.REQUEST_CONFLICT", "error.INVALID_REQUEST", "error.INVALID_MEMBER", "error.ROOM_ARCHIVED"]);
function errorMessage(error: unknown): string {
  if (error instanceof RoomRequestError) {
    const key = `error.${error.code}` as MessageKey;
    if (errorKeys.has(key)) return t(key);
    if (error.status === 401) return t("error.AUTH_REQUIRED");
    if (error.status === 403 || error.status === 404) return t("error.ACCESS_DENIED");
  }
  return t("error.UNAVAILABLE");
}
function command() { return { request_id: crypto.randomUUID() }; }
function FormPanel({ title, children }: { title: string; children: ReactNode }) { return <section className={styles.panel}><h2>{title}</h2>{children}</section>; }

function Login({ authenticate }: { authenticate: Authenticate }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [register, setRegister] = useState(false); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  async function login(mode: "login" | "register" | "google") {
    if (busy) return;
    setBusy(true); setNotice("");
    try {
      const outcome = await authenticate(mode, email, password);
      if (outcome === "signed-in") window.location.reload();
      else { setNotice(t("auth.verify")); setRegister(false); setPassword(""); }
    } catch { setNotice(t("auth.failed")); }
    finally { setBusy(false); }
  }
  return <FormPanel title={t("auth.title")}>
    <p>{t("auth.description")}</p>
    <form className={styles.form} onSubmit={e => { e.preventDefault(); void login(register ? "register" : "login"); }}>
      <label>{t("auth.email")}<input required type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label>{t("auth.password")}<input required type="password" autoComplete={register ? "new-password" : "current-password"} minLength={register ? 8 : undefined} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button disabled={busy} type="submit">{t(register ? "auth.register" : "auth.login")}</button>
      <button disabled={busy} type="button" onClick={() => setRegister(!register)}>{t(register ? "auth.login" : "auth.register")}</button>
      <button disabled={busy} type="button" onClick={() => void login("google")}>{t("auth.google")}</button>
    </form>{notice && <p role="status">{notice}</p>}
  </FormPanel>;
}
function RoomForm({ initial, busy, ceiling, onSubmit }: { initial?: Room; busy: boolean; ceiling: number; onSubmit: (data: { name: string; slug: string; capacity: number; interior: Interior }) => void }) {
  const [name, setName] = useState(initial?.name ?? ""); const [slug, setSlug] = useState(initial?.slug ?? "");
  const [capacity, setCapacity] = useState(initial?.capacity ?? Math.min(3, ceiling)); const [interior, setInterior] = useState<Interior>(initial?.interior ?? "apartment");
  return <form className={styles.form} onSubmit={e => { e.preventDefault(); onSubmit({ name, slug, capacity, interior }); }}>
    <label>{t("room.name")}<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label>
    <label>{t("room.slug")}<input required minLength={3} maxLength={48} pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" disabled={!!initial} value={slug} onChange={e => setSlug(e.target.value)} /></label>
    <label>{t("room.capacity")}<input required type="number" min={2} max={ceiling} value={capacity} onChange={e => setCapacity(Number(e.target.value))} /></label>
    <label>{t("room.interior")}<select value={interior} onChange={e => setInterior(e.target.value as Interior)}>{INTERIORS.map(id => <option key={id} value={id}>{t(`interior.${id}`)}</option>)}</select></label>
    <button type="submit" disabled={busy}>{t(initial ? "room.save" : "room.create")}</button>
  </form>;
}
function PlatformAdmin({ identity, busy, run }: { identity: Identity; busy: boolean; run: (path: string, body: object) => Promise<void> }) {
  const [uid, setUid] = useState(""); const [limits, setLimits] = useState<Limits>(identity.limits);
  return <FormPanel title={t("admin.title")}>
    <form className={styles.form} onSubmit={e => { e.preventDefault(); void run("admin/approval", { ...command(), uid, approved: true }); }}>
      <label>{t("admin.uid")}<input required maxLength={128} value={uid} onChange={e => setUid(e.target.value)} /></label>
      <button disabled={busy}>{t("admin.approve")}</button><button type="button" disabled={busy || !uid} onClick={() => void run("admin/approval", { ...command(), uid, approved: false })}>{t("admin.revoke")}</button>
    </form>
    <form className={styles.form} onSubmit={e => { e.preventDefault(); void run("admin/limits", { ...command(), ...limits }); }}>
      {(Object.keys(limits) as (keyof Limits)[]).map(key => <label key={key}>{t(`limit.${key}`)}<input required type="number" min={key === "storage_rooms" || key === "active_rooms" ? 1 : 2} max={{storage_rooms:300,active_rooms:30,active_participants:100,capacity_ceiling:10}[key]} value={limits[key]} onChange={e => setLimits(old => ({ ...old, [key]: Number(e.target.value) }))} /></label>)}
      <button disabled={busy}>{t("room.save")}</button>
    </form><p>{t("admin.pending")}</p>
  </FormPanel>;
}
function MemberRow({ item, owner, busy, action }: { item: NonNullable<Room["members"]>[number]; owner: boolean; busy: boolean; action: (name: string, data: object) => void }) {
  const [roles, setRoles] = useState<Role[]>(item.roles);
  return <li className={styles.member}><code>{item.uid}</code> <span>{t(item.owner ? "role.owner" : item.status === "active" ? "role.member" : item.status === "blocked" ? "member.blocked" : "member.removed")}</span>
    {!item.owner && <>{owner && item.status === "active" && <><div className={styles.roles}>{ROLES.map(role => <label key={role}><input type="checkbox" checked={roles.includes(role)} onChange={e => setRoles(old => e.target.checked ? [...old, role] : old.filter(v => v !== role))} />{t(`role.${role}`)}</label>)}</div><button disabled={busy} onClick={() => action("roles", { uid: item.uid, roles })}>{t("room.save")}</button><button disabled={busy} onClick={() => action("propose_transfer", { uid: item.uid })}>{t("member.transfer")}</button></>}
    {item.status === "active" && <><button disabled={busy} onClick={() => action("remove", {uid:item.uid})}>{t("member.remove")}</button><button disabled={busy} onClick={() => action("block", {uid:item.uid})}>{t("member.block")}</button></>}
    {item.status === "blocked" && <button disabled={busy} onClick={() => action("unblock", {uid:item.uid})}>{t("member.unblock")}</button>}</>}
  </li>;
}
function RoomPanel({ room, identity, busy, run, invitation }: { room: Room; identity: Identity; busy: boolean; run: (path: string, data: object) => Promise<void>; invitation: string }) {
  const [target, setTarget] = useState(""); const [kind, setKind] = useState<"uid" | "email">("email"); const [days, setDays] = useState(7);
  const [copied, setCopied] = useState(false);
  function action(name: string, data: object = {}) { void run(`rooms/${room.slug}/${name}`, { ...command(), version: room.version, ...data }); }
  const link = typeof window === "undefined" ? `${ROOM_ROOT}/r/${room.slug}` : `${window.location.origin}${ROOM_ROOT}/r/${room.slug}`;
  return <>
    <FormPanel title={room.name}><p>{room.status === "archived" ? t("room.archived") : t("room.lounge")}</p><p>{t("room.capacity")}: {room.capacity}</p><p>{t(`interior.${room.interior}`)}</p><label>{t("room.link")}<input readOnly value={link} onFocus={e => e.currentTarget.select()} /></label><button type="button" onClick={() => { void navigator.clipboard.writeText(link).then(() => setCopied(true)).catch(() => setCopied(false)); }}>{t(copied ? "room.copied" : "room.copy")}</button><p>{t("room.pending")}</p></FormPanel>
    {room.is_owner && <FormPanel title={t("room.manage")}>{room.status === "active" ? <><RoomForm key={room.version} initial={room} ceiling={identity.limits.capacity_ceiling} busy={busy} onSubmit={({name,capacity,interior}) => action("update", {name,capacity,interior})} /><button disabled={busy} onClick={() => { if (window.confirm(t("room.archive_confirm"))) action("archive"); }}>{t("room.archive")}</button></> : <button disabled={busy} onClick={() => action("restore")}>{t("room.restore")}</button>}</FormPanel>}
    {!room.is_owner && room.status === "active" && room.roles.includes("designer") && <FormPanel title={t("room.interior")}><select aria-label={t("room.interior")} value={room.interior} disabled={busy} onChange={e => action("design", {interior:e.target.value})}>{INTERIORS.map(id => <option key={id} value={id}>{t(`interior.${id}`)}</option>)}</select></FormPanel>}
    {room.status === "active" && room.can_invite && <FormPanel title={t("invite.title")}><form className={styles.form} onSubmit={e => { e.preventDefault(); action("invite", {target_kind:kind,target,days}); }}><label>{t("invite.kind")}<select value={kind} onChange={e => { setKind(e.target.value as "uid"|"email");setTarget(""); }}><option value="email">{t("auth.email")}</option><option value="uid">UID</option></select></label><label>{t("invite.target")}<input required type={kind === "email" ? "email" : "text"} maxLength={254} value={target} onChange={e => setTarget(e.target.value)} /></label><label>{t("invite.days")}<input type="number" required min={1} max={30} value={days} onChange={e => setDays(Number(e.target.value))} /></label><button disabled={busy}>{t("invite.create")}</button></form>{invitation && <><p>{t("invite.once")}</p><input aria-label={t("invite.link")} readOnly value={invitation} onFocus={e => e.currentTarget.select()} /><button onClick={() => { void navigator.clipboard.writeText(invitation).catch(() => undefined); }}>{t("room.copy")}</button></>}<ul>{room.invites?.map(item => <li key={item.id}>{t(item.status === "pending" ? "invite.pending" : item.status === "consumed" ? "invite.consumed" : "invite.revoked")} — {new Date(item.expires_at_ms).toLocaleDateString("ru")} {item.status === "pending" && <button disabled={busy} onClick={() => action("revoke_invite", {invite_id:item.id})}>{t("invite.revoke")}</button>}</li>)}</ul></FormPanel>}
    {room.status === "active" && room.members && <FormPanel title={t("member.title")}><ul className={styles.members}>{room.members.map(item => <MemberRow key={`${room.version}:${item.uid}`} item={item} owner={room.is_owner} busy={busy} action={action} />)}</ul></FormPanel>}
    {room.status === "active" && room.transfer && <FormPanel title={t("member.transfer")}>{room.transfer.target === identity.uid ? <button disabled={busy} onClick={() => action("accept_transfer", {transfer_id:room.transfer?.id})}>{t("member.accept")}</button> : <button disabled={busy} onClick={() => action("cancel_transfer")}>{t("member.cancel")}</button>}</FormPanel>}
  </>;
}
export function SamePlaceRoomCore({ slug, token, authenticate, signOut }: Props) {
  const [identity, setIdentity] = useState<Identity | null>(null); const [catalogue, setCatalogue] = useState<Catalogue | null>(null); const [room, setRoom] = useState<Room | null>(null);
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [invitation, setInvitation] = useState(""); const [revision, setRevision] = useState(0);
  const inFlight = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const person = await roomRequest<Identity>("identity", undefined, controller.signal);
        if (!controller.signal.aborted) setIdentity(person);
        const data = token ? null : slug ? await roomRequest<Room>(`rooms/${slug}`, undefined, controller.signal) : await roomRequest<Catalogue>("rooms", undefined, controller.signal);
        if (!controller.signal.aborted) { setIdentity(person); if (slug) setRoom(data as Room); else setCatalogue(data as Catalogue | null); setError(""); }
      } catch (cause) {
        if (!controller.signal.aborted) { if (cause instanceof RoomRequestError && cause.status === 401) setIdentity(null); setRoom(null); setCatalogue(null); setError(errorMessage(cause)); }
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [slug, token, revision]);
  async function run(path: string, data: object) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(""); setInvitation("");
    try {
      const result = await roomRequest<Room>(path, data);
      if (result.invitation_token) setInvitation(`${window.location.origin}${ROOM_ROOT}/j#${result.invitation_token}`);
      if ((path === "rooms" || path === "redeem") && result.slug) { window.location.assign(`${ROOM_ROOT}/r/${result.slug}`); return; }
      if (slug && result.slug === slug) setRoom(result);
      else setRevision(old => old + 1);
    } catch (cause) {
      setError(errorMessage(cause));
      if (cause instanceof RoomRequestError && [401,403,404].includes(cause.status)) { if (cause.status === 401) setIdentity(null);setRoom(null);setCatalogue(null); }
    } finally { inFlight.current = false;setBusy(false); }
  }
  async function logout(event: FormEvent) { event.preventDefault(); setIdentity(null);setRoom(null);setCatalogue(null);setInvitation(""); try { await signOut(); window.location.reload(); } catch { setError(t("error.UNAVAILABLE")); } }
  return <section className={styles.shell} lang="ru" aria-labelledby="sameplace-title"><header><h1 id="sameplace-title">SamePlace</h1><p>{t("foundation.motto")}</p><nav><Link prefetch={false} href={`${ROOM_ROOT}/rooms`}>{t("room.list")}</Link>{identity && <form onSubmit={e => void logout(e)}><button disabled={busy} type="submit">{t("auth.logout")}</button></form>}</nav></header>
    {loading && <p role="status">{t("room.loading")}</p>}{error && <p role="alert">{error}</p>}
    {!loading && !identity && <Login authenticate={authenticate} />}
    {identity && <><p className={styles.identity}>{t("auth.uid")}: <code>{identity.uid}</code></p><button disabled={busy} onClick={() => {setRoom(null);setCatalogue(null);setInvitation("");setRevision(old=>old+1);}}>{t("room.refresh")}</button>
    {token ? <FormPanel title={t("invite.accept_title")}><p>{t("invite.accept_description")}</p><button disabled={busy} onClick={() => void run("redeem", {...command(),token})}>{t("invite.accept")}</button></FormPanel> : room ? <RoomPanel room={room} identity={identity} busy={busy} run={run} invitation={invitation} /> : catalogue && <><FormPanel title={t("room.list")}><ul>{catalogue.rooms.map(item => <li key={item.id}><Link prefetch={false} href={`${ROOM_ROOT}/r/${item.slug}`}>{item.name}</Link> — {t(item.status === "archived" ? "room.archived" : "room.active")}</li>)}</ul>{!catalogue.rooms.length && <p>{t("room.empty")}</p>}</FormPanel>{catalogue.can_create ? <FormPanel title={t("room.create")}><RoomForm busy={busy} ceiling={identity.limits.capacity_ceiling} onSubmit={data => void run("rooms", {...command(), ...data})}/></FormPanel> : <p>{t("room.approval_required")}</p>}{identity.platform_owner && <PlatformAdmin identity={identity} busy={busy} run={run} />}</>}
    </>}
  </section>;
}

export function InvalidRoomInvitation({ loading = false }: { loading?: boolean }) { return <section className={styles.shell} lang="ru"><p role={loading ? "status" : "alert"}>{t(loading ? "room.loading" : "error.INVITE_INVALID")}</p><Link prefetch={false} href={`${ROOM_ROOT}/rooms`}>{t("room.list")}</Link></section>; }
