"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import {
  ApiError, adjustRoom, createRoom, invitation, joinRoom, newKey, roomView,
  sendCommand, settleRoom, startRoom,
} from "./room-client";
import {
  allowedToAct, cardId, cardLabel,
  phaseLabel, ROOM_ID_RE, statusMessage,
  type Card, type CommandAction, type RoomInvitation, type RoomView, type TableTheme,
} from "./game-model.ru";
import styles from "./preferans-game.module.css";
import { PreferansControls } from "./PreferansControls.ru";
import { LiveMediaControls, MediaSeatTile, useLiveMedia } from "./LiveMedia.ru";
import { connectRealtime, type Presence } from "./realtime-client";
import { CardArtwork } from "./CardArtwork.ru";
import { GameTable } from "./GameTable.ru";
import { SharedRoom, SharedObjects, type SharedCommand } from "./SharedRoom.ru";
import { replayMoveAllowed, type OverlayKind } from "./presentation-model";
import { ProjectSidebar as ImmersiveMenu } from "./ProjectSidebar.ru";
import { Deck } from "./Deck.ru";
import { attachCardPointerDrag } from "./pointer-drag";
import { CardBackContext } from "./CardBackTheme";
import { type BackTheme, type DragIntent, isBackTheme, legalDrop, matchingDrag, mayStart, mayPassDeck, dealerFor, changeDraft } from "./table-interaction";
import { Lobby } from "./Lobby.ru";
import { PreferansHistory } from "./PreferansHistory.ru";
import { SheetExit } from "./SheetExit.ru";
import { effectiveOpacity, parseTransparency } from "./table-details";
import { safeProfiles, type Seat, type SeatProfile } from "./table-model";
import { LobbySetup } from "./LobbySetup.ru";
import { SeatSwap } from "./SeatSwap.ru";
import { BidPanel } from "./BidPanel.ru";
import { CycleSetting } from "./CycleSetting.ru";
import { DealStatus } from "./DealStatus.ru";
import { orderHand, ownCards, type SortMode } from "./interaction-model";
import { autoSettlementAllowed } from "./table-pr20";
import { fallbackDelay, gameCooldown } from "./transport-budget";

import { ReleaseControls } from "./ReleaseControls.ru";
import { RulesetEditor } from "./RulesetEditor.ru";

const REALTIME_ENABLED = process.env.NEXT_PUBLIC_PREFERANS_REALTIME_ENABLED === "true";
const LIVE_MEDIA_ENABLED = process.env.NEXT_PUBLIC_PREFERANS_MEDIA_ENABLED === "true" && process.env.NEXT_PUBLIC_PREFERANS_LIVE_MEDIA_WS_ENABLED === "true";

type Mutation = { label: string; run: () => Promise<unknown> };
const seatNames = ["Игрок 1", "Игрок 2", "Игрок 3"];
const statusNames: Record<RoomView["status"], string> = {
  lobby: "Ожидание игроков", playing: "Идёт игра",
  awaiting_settlement: "Подсчёт результатов", between: "Между раздачами", closed: "Партия завершена", archived: "Партия архивирована",
};

function CardFace({ card, selected, playable, pendingPlay, onClick, onDragStart, onDragOver, onDrop, onDragEnd, onKeyDown }: {
  card: Card; selected?: boolean; playable?: boolean; pendingPlay?:boolean; onClick?: () => void;
  onDragStart?: (event: DragEvent<HTMLButtonElement>) => void;
  onDragOver?: (event: DragEvent<HTMLButtonElement>) => void;
  onDrop?: (event: DragEvent<HTMLButtonElement>) => void;
  onDragEnd?: ()=>void;
  onKeyDown?: (event: import("react").KeyboardEvent<HTMLButtonElement>)=>void;
}) {
  const red = card.suit === "D" || card.suit === "H";
  return (
    <button type="button" className={`${styles.playingCard} ${red ? styles.red : ""} ${selected ? styles.selected : ""} ${playable ? styles.playable : ""}`}
      aria-label={`${cardLabel(card)}${selected ? ", выбрана" : ""}`}
      aria-pressed={Boolean(selected)} disabled={!onClick && !onDragStart} onClick={onClick}
      draggable={Boolean(onDragStart)} onDragStart={onDragStart} onDragOver={onDragOver} onDrop={onDrop} onDragEnd={onDragEnd} onKeyDown={onKeyDown}
      data-card={cardId(card)} data-pending-play={pendingPlay?"true":undefined}>
      <CardArtwork card={card} decorative />
    </button>
  );
}

function ActionPanel({ view, busy, selectedCards, command, profiles,
  regularRoute, setRegularRoute, onStart, onSettle }: {
  view: RoomView; busy: boolean; selectedCards: Card[]; profiles:SeatProfile[]|null;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
  regularRoute: "pool" | "hill_first"; setRegularRoute: (x: "pool" | "hill_first") => void;
  onStart: () => void; onSettle: () => void;
}) {
  const myTurn = allowedToAct(view);
  if (view.status === "playing" && (view.controls?.undo || (view.controls?.paused && !replayMoveAllowed(view)))) {
    return null;
  }
  if (view.status === "between" && view.next_deal && REALTIME_ENABLED) {
    return <section className={styles.actionPanel}><h3>Новая раздача</h3><DealStatus view={view}/></section>;
  }
  if (view.status === "lobby" || view.status === "between") {
    return <section className={styles.actionPanel} aria-labelledby="preferans-actions"><h3 id="preferans-actions">{view.status === "lobby" ? "Сбор игроков" : "Новая раздача"}</h3>
      {view.status==="lobby"&&<p>Занято мест: {view.occupied.filter(Boolean).length} из 3.</p>}
      {(view.room_admin || (view.my_seat!==null&&dealerFor(view)===view.my_seat)) && <button type="button" className={styles.primary} disabled={busy || !mayStart(view)} onClick={onStart}>Раздать карты</button>}
    </section>;
  }
  if (view.status === "awaiting_settlement") {
    if(view.settlement_options?.regular_choice===false)return null;
    if(!view.settlement_options)return view.room_admin?<button type="button" className={styles.primary} disabled={busy||Boolean(view.controls?.paused||view.controls?.undo)} onClick={onSettle}>Рассчитать раздачу</button>:null;
    return <section className={styles.actionPanel} aria-labelledby="preferans-actions"><h3 id="preferans-actions">Сдача завершена</h3>
      <p>Раздача ожидает начисления пули, горы и вистов.</p>
      {view.my_seat===view.declarer ? <>
        {view.settlement_options?.regular_choice && <label className={styles.field}>Куда записать выигрыш
          <select value={regularRoute} onChange={(e: ChangeEvent<HTMLSelectElement>) => setRegularRoute(e.target.value as "pool" | "hill_first")}>
            <option value="pool">Помочь соперникам</option><option value="hill_first">Сначала погасить гору</option></select></label>}
        <button type="button" disabled={busy || Boolean(view.controls?.paused || view.controls?.undo)} className={styles.primary} onClick={onSettle}>Рассчитать раздачу</button>
      </> : <p className={styles.subtle}>Ожидаем решение заказчика.</p>}
    </section>;
  }
  if (view.status === "archived") return <section className={styles.actionPanel}><h3>Партия архивирована</h3><p>Без игрового поражения, медалей и расчёта незакрытой пули.</p></section>;
  if (view.status === "closed" && view.sheet_loser !== undefined) return null;
  if (view.status === "closed") return <section className={styles.actionPanel}>
    {view.sheet_loser !== undefined ? null : <><h3>Пуля закрыта</h3><p>Все три игрока закрыли пули. Итоговая партия завершена.</p></>}
  </section>;
  if (view.phase === "misere_offer") {
    const name = profiles?.[view.declarer??-1]?.name || seatNames[view.declarer??0];
    return <section className={`${styles.actionPanel} ${styles.compactAction}`} aria-label="Предложение сыгранного мизера">
      {myTurn?<div className={styles.actions}>
        <button type="button" className={styles.primary} disabled={busy} onClick={()=>command("misere_vote",{approve:true})}>Согласен, {name} сыграл мизер.</button>
        <button type="button" disabled={busy} onClick={()=>command("misere_vote",{approve:false})}>Да хрен там, играем!!!</button>
      </div>:<p>Ждём согласия соперников: {view.misere_offer?.approved.length??0}/2.</p>}
    </section>;
  }
  if (!myTurn || view.phase === "play" || view.phase === "opening_lead") return null;
  return <section className={`${styles.actionPanel} ${styles.compactAction}`} aria-label="Игровое действие">
    {view.phase === "auction" && <>
      <BidPanel key={`${view.game_id}:auction`} view={view} busy={busy} command={command}/>
    </>}
    {view.phase === "discard" && <>
      <p>Перетащи две карты в снос</p>
      <button type="button" className={styles.primary} disabled={busy || selectedCards.length !== 2}
        onClick={() => command("discard", { cards: selectedCards })}>Снести две карты</button>
    </>}
    {view.phase === "declare" && <>
      <p>Объяви игру</p>
      <BidPanel key={`${view.game_id}:declare`} view={view} busy={busy} command={command}/>
    </>}
    {(["defense_first", "defense_second", "defense_reconsider"] as string[]).includes(view.phase ?? "") && <>
      <div className={styles.actions}>
        <button type="button" className={styles.primary} disabled={busy} onClick={() => command("defense", { decision: "vist" })}>Вист</button>
        <button type="button" disabled={busy} onClick={() => command("defense", { decision: "pass" })}>Пас</button>
        {view.phase === "defense_second" && view.defense?.[(view.declarer! + 1) % 3] === "pass" &&
          (view.contract?.level === 6 || view.contract?.level === 7) &&
          <button type="button" disabled={busy} onClick={() => command("defense", { decision: "half" })}>Полвиста</button>}
      </div>
    </>}
    {view.phase === "choose_mode" && <>
      <p>Светлая игра открывает карты пасовавшего, и вистующий управляет ими. В тёмную каждый ходит сам.</p>
      <div className={styles.actions}>
        <button type="button" className={styles.primary} disabled={busy} onClick={() => command("mode", { mode: "open" })}>В светлую</button>
        <button type="button" disabled={busy} onClick={() => command("mode", { mode: "closed" })}>В тёмную</button>
      </div>
    </>}
  </section>;
}

export function PreferansGame({preferenceScope}: {preferenceScope?: string} = {}) {
  const [roomId, setRoomId] = useState("");
  const liveMedia = useLiveMedia();
  const {bind: bindMedia, receive: receiveMedia} = liveMedia;
  const [view, setView] = useState<RoomView | null>(null);
  const [invited, setInvited] = useState<RoomInvitation | null>(null);
  const viewRef = useRef<RoomView | null>(null);
  const serverOffset = useRef(0);
  const serverNow = useCallback(() => Date.now() + serverOffset.current, []);
  const [status, setStatus] = useState("");
  const [dropNotice,setDropNotice]=useState("");
  useEffect(()=>{if(!dropNotice)return;const timer=setTimeout(()=>setDropNotice(""),3000);return()=>clearTimeout(timer);},[dropNotice]);
  const [online, setOnline] = useState(true);
  const [rtReady, setRtReady] = useState(false);
  const [rtPresence, setRtPresence] = useState<Presence[] | null>(null);
  const [profileState, setProfileState] = useState<{ room: string; seats: string; profiles: SeatProfile[] } | null>(null);
  const occupiedKey = view ? `${view.occupied.map(v => v ? "1" : "0").join("")}:${view.seat_revision ?? 0}` : "";
  const profileRoom = view && view.my_seat !== null ? view.room_id : "";
  const profiles = profileState && profileState.room === profileRoom && profileState.seats === occupiedKey ? profileState.profiles : null;
  useEffect(() => {
    if (!profileRoom) return;
    const controller = new AbortController();
    fetch(`/api/preferans/rooms/${profileRoom}/profiles`, { credentials:"same-origin", cache:"no-store", signal:controller.signal })
      .then(async response => response.ok ? safeProfiles(await response.json()) : null)
      .then(data => { if (data && !controller.signal.aborted) setProfileState({room:profileRoom,seats:occupiedKey,profiles:data}); })
      .catch(() => undefined);
    return () => controller.abort();
  }, [profileRoom, occupiedKey]);
  const activeRoomRef = useRef("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Mutation | null>(null);
  const [pollKey, setPollKey] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [pendingPlay,setPendingPlay]=useState<{room:string;game:string|null;version:number;owner:number;card:Card}|null>(null);
  const [order, setOrder] = useState<string[]>([]);
  const [sortMode, setSortMode] = useState<SortMode>("grouped");
  const sortKey = preferenceScope ? `preferans:sort:${preferenceScope}` : null;
  useEffect(() => {
    if (!sortKey) return;
    try { setSortMode(window.localStorage.getItem(sortKey) === "suit" ? "suit" : "grouped"); }
    catch { /* Local storage can be disabled. */ }
  }, [sortKey]);
  const changeSort = (mode: SortMode) => {
    setSortMode(mode); setOrder([]);
    if (sortKey) try { window.localStorage.setItem(sortKey, mode); } catch { /* Optional preference. */ }
  };
  const [regularRoute, setRegularRoute] = useState<"pool" | "hill_first">("pool");
  const [localTableTheme,setLocalTableTheme] = useState<TableTheme | "room">("room");
  const tableKey = preferenceScope ? `preferans:table:${preferenceScope}` : null;
  const transparencyKey=preferenceScope?`preferans:transparency:${preferenceScope}`:null;
  const [transparency,setTransparency]=useState<number|null>(null);
  useEffect(()=>{if(transparencyKey)try{setTransparency(parseTransparency(localStorage.getItem(transparencyKey)));}catch{/* Optional preference. */}},[transparencyKey]);
  const changeTransparency=(value:number)=>{setTransparency(value);if(transparencyKey)try{localStorage.setItem(transparencyKey,String(value));}catch{/* Optional preference. */}};
  const selectedTheme=localTableTheme==="room"?view?.table_theme??"felt":localTableTheme;
  const opacity=effectiveOpacity(selectedTheme,transparency);
  useEffect(()=>{if(tableKey)try{const saved=localStorage.getItem(tableKey);if(saved==="felt"||saved==="blue"||saved==="wood"||saved==="glass")setLocalTableTheme(saved);else setLocalTableTheme("room");}catch{/* Optional preference. */}},[tableKey]);
  const changeTableTheme=(theme:TableTheme|"room")=>{setLocalTableTheme(theme);if(tableKey)try{localStorage.setItem(tableKey,theme);}catch{/* Optional preference. */}};
  useEffect(()=>attachCardPointerDrag(document),[]);
  const dragging = useRef<DragIntent | null>(null);
  const inFlight = useRef(false);
  const [back,setBack] = useState<BackTheme>("classic");
  const [peekDiscard,setPeekDiscard] = useState(false);
  const themeKey = preferenceScope ? `preferans:back:${preferenceScope}` : null;
  useEffect(()=>{try { const saved=themeKey?localStorage.getItem(themeKey):null; if(isBackTheme(saved))setBack(saved); } catch { /* Optional preference. */ }},[themeKey]);
  const changeBack=(value:BackTheme)=>{setBack(value);if(themeKey)try{localStorage.setItem(themeKey,value);}catch{/* Optional preference. */}};

  const updateView = useCallback((next: RoomView) => {
    if (activeRoomRef.current !== next.room_id) return;
    if (viewRef.current?.room_id === next.room_id && viewRef.current.version > next.version) return;
    viewRef.current = next;
    setView(next);
    setInvited(null);
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get("room");
    const initial = fromUrl && ROOM_ID_RE.test(fromUrl) ? fromUrl : "";
    activeRoomRef.current = initial;
    setRoomId(initial);
  }, []);

  const openRoom = useCallback((id: string) => {
    if (!ROOM_ID_RE.test(id)) { setStatus("Нужен идентификатор комнаты из 32 символов (0–9, a–f)."); return; }
    bindMedia(0, null);
    viewRef.current = null;
    activeRoomRef.current = id;
    setProfileState(null);
    setView(null); setInvited(null); setSelected([]); setOrder([]);
    setRtReady(false); setRtPresence(null);
    setStatus(""); setRoomId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("room", id);
    window.history.replaceState({}, "", url);
    setPollKey(v => v + 1);
  }, [bindMedia]);

  const leaveRoom = useCallback(() => {
    bindMedia(0, null);
    viewRef.current = null;
    activeRoomRef.current = "";
    setProfileState(null);
    setRoomId(""); setView(null); setInvited(null); setSelected([]); setStatus("");
    setRtReady(false); setRtPresence(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("room");
    window.history.replaceState({}, "", url);
  }, [bindMedia]);

  // HTTP bootstrap and bounded fallback. Healthy sockets own room delivery.
  useEffect(() => {
    if (!roomId || rtReady) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let errors = 0;
    async function tick() {
      let nextMs = fallbackDelay(viewRef.current?.status, document.visibilityState === "hidden", errors);
      try {
        if (gameCooldown.remaining()) { setOnline(false); setStatus(statusMessage(503)); return; }
        const result = await roomView(roomId, viewRef.current?.version);
        if (stopped) return;
        if (!("unchanged" in result)) {
          if (result.presentation) serverOffset.current = result.presentation.server_now_ms - Date.now();
          updateView(result);
          setStatus("");
        }
        setOnline(true);
        errors = 0;
        nextMs = fallbackDelay(viewRef.current?.status, document.visibilityState === "hidden");
        if (viewRef.current?.status === "archived") stopped = true;
      } catch (error) {
        if (stopped) return;
        if (error instanceof ApiError && error.status === 404 && !viewRef.current) {
          try {
            const found = await invitation(roomId);
            if (!stopped) { setInvited(found); setOnline(true); setStatus(""); errors = 0; }
          } catch (inviteError) {
            if (!stopped) setStatus(inviteError instanceof ApiError ? statusMessage(inviteError.status) : statusMessage(503));
          }
        } else {
          errors += 1;
          setOnline(false);
          if (error instanceof ApiError) setStatus(statusMessage(error.status));
          else setStatus(statusMessage(503));
          if (error instanceof ApiError && [401, 403].includes(error.status)) {
            // Stop the finally-scheduled poll and clear previously authorized private state.
            stopped = true;
            viewRef.current = null; setView(null); setInvited(null);
            return;
          }
        }
        nextMs = fallbackDelay(viewRef.current?.status, document.visibilityState === "hidden", Math.max(1, errors));
      } finally {
        if (!stopped) {
          timer = setTimeout(tick, Math.max(nextMs, gameCooldown.remaining(), document.visibilityState === "hidden" ? 60_000 : 0));
        }
      }
    }
    void tick();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
  }, [roomId, pollKey, updateView, rtReady]);

  const mySeat = view?.my_seat;
  const archived = view?.status === "archived";
  useEffect(() => { if (archived) { bindMedia(0, null); setRtReady(false); setRtPresence(null); } }, [archived, bindMedia]);
  useEffect(() => {
    if (!REALTIME_ENABLED || !roomId || mySeat === null || mySeat === undefined || archived) return;
    return connectRealtime(roomId, mySeat, {
      onMediaTransport: LIVE_MEDIA_ENABLED ? sender => { if (activeRoomRef.current === roomId) bindMedia(mySeat, sender); } : undefined,
      onMediaFrame: LIVE_MEDIA_ENABLED ? frame => { if (activeRoomRef.current === roomId) receiveMedia(frame); } : undefined,
      onClock: at => { if (activeRoomRef.current === roomId) serverOffset.current = at - Date.now(); },
      onView: next => { if (activeRoomRef.current === roomId) { updateView(next); setOnline(true); } },
      onReady: ready => { if (activeRoomRef.current === roomId) { setRtReady(ready); if (!ready) { setRtPresence(null); setOnline(false); } } },
      onPresence: value => { if (activeRoomRef.current === roomId) setRtPresence(value); },
      onDenied: () => {
        if (activeRoomRef.current !== roomId) return;
        viewRef.current = null; setView(null); setInvited(null); setOnline(false);
        setStatus(statusMessage(403));
      },
    });
  }, [roomId, mySeat, updateView, bindMedia, receiveMedia, archived]);

  // Presence leases are server-persisted. A stale lease conservatively pauses a counter.
  // No browser clock can apply a financial penalty or decide who is online.
  useEffect(() => {
    if (!roomId || rtReady || view?.my_seat === null || view?.my_seat === undefined ||
        (!REALTIME_ENABLED && view?.status !== "playing") || view?.status === "closed" || view?.status === "archived") return;
    let stopped = false;
    let inProgress = false;
    async function heartbeat() {
      if (stopped || inProgress || gameCooldown.remaining()) return;
      const current = viewRef.current;
      if (!current || current.status === "closed" || current.status === "archived" || (!REALTIME_ENABLED && current.status !== "playing")) return;
      inProgress = true;
      try {
        const response = await sendCommand(current.room_id, newKey(), current.version, "pulse", {});
        if (!stopped && response.version > current.version) setPollKey(value => value + 1);
      } catch (error) {
        // Other players can update the room between our view and heartbeat.
        // The next ordinary poll fetches the new version; never guess it here.
        if (!stopped && error instanceof ApiError && error.status === 409) setPollKey(v => v + 1);
      } finally { inProgress = false; }
    }
    void heartbeat();
    const interval = setInterval(() => { void heartbeat(); }, 45_000);
    return () => { stopped = true; clearInterval(interval); };
  }, [roomId, view?.game_id, view?.my_seat, view?.status, rtReady]);

  const nextDeadline = view?.next_deal?.deadline_ms;
  useEffect(() => {
    if (!REALTIME_ENABLED || rtReady || !roomId || view?.my_seat == null || typeof nextDeadline !== "number") return;
    let disposed = false;
    const timer = setTimeout(() => {
      const current = viewRef.current;
      if (!current || current.room_id !== roomId || current.status !== "between" || current.next_deal?.deadline_ms !== nextDeadline) return;
      void sendCommand(roomId, newKey(), current.version, "pulse", {}).then(response => {
        if (!disposed && response.version > current.version) setPollKey(v => v + 1);
      }).catch(() => { /* Existing bounded fallback remains responsible for recovery. */ });
    }, Math.max(250, Math.min(5500, nextDeadline - Date.now() + 100)));
    return () => { disposed = true; clearTimeout(timer); };
  }, [roomId, view?.my_seat, nextDeadline, rtReady]);

  useEffect(() => {
    setSelected([]); setPeekDiscard(false); dragging.current=null;
  }, [view?.room_id, view?.game_id, view?.phase, view?.turn, view?.controller, view?.played_tricks]);

  useEffect(() => { setOrder([]); }, [view?.room_id, view?.game_id]);

  const mutate = useCallback(async (label: string, run: () => Promise<unknown>) => {
    if (busy || inFlight.current) return;
    inFlight.current=true;
    setBusy(true); setStatus("");
    const candidate = { label, run };
    setPending(candidate);
    try {
      const result = await run();
      setPending(null);
      if (result && typeof result === "object" && "room_id" in result && typeof result.room_id === "string") {
        const id = result.room_id;
        if (roomId !== id) openRoom(id);
        else {
          // Healthy sockets normally deliver first. One recovery read only if a
          // committed play is still missing locally after 350ms.
          if(label==="play"&&rtReady&&"version" in result&&typeof result.version==="number"){
            const version=result.version;
            if((viewRef.current?.version??-1)<version){
              await new Promise<void>(resolve=>setTimeout(resolve,350));
              if(activeRoomRef.current===id&&(viewRef.current?.version??-1)<version){
                try{const next=await roomView(id,viewRef.current?.version);if(!("unchanged" in next))updateView(next);else setPendingPlay(null);}catch{setPendingPlay(null);}
              }
            }
          }
          setPollKey(v => v + 1);
        }
      } else setPollKey(v => v + 1);
    } catch (error) {
      setPendingPlay(null);
      const code = error instanceof ApiError ? error.status : 503;
      setStatus(statusMessage(code));
      if ([401, 403, 404, 409, 422].includes(code)) setPending(null);
      if (code === 409) setPollKey(v => v + 1);
    } finally { inFlight.current=false; setBusy(false); }
  }, [busy, openRoom, roomId, rtReady, updateView]);

  const create = () => {
    const token = newKey();
    void mutate("создание комнаты", () => createRoom(token));
  };
  const join = () => {
    if (!invited) return;
    const token = newKey();
    void mutate("вход в комнату", () => joinRoom(invited.room_id, token, invited.version));
  };
  const start = () => {
    if (!view || !mayStart(view)) return;
    const token = newKey();
    void mutate("раздача карт", () => startRoom(view.room_id, token, view.version));
  };
  const command = (action: CommandAction, args: Record<string, unknown> = {}) => {
    if (!view) return;
    const token = newKey();
    void mutate(action, () => sendCommand(view.room_id, token, view.version, action, args));
  };
  const settle = () => {
    if (!view) return;
    const token = newKey();
    const routes: Array<"pool"|"hill_first"|"help"> = view.settlement_options?.passout_defaults ?? ["pool", "pool", "pool"];
    const route = view.settlement_options?.regular_choice ? regularRoute : "pool";
    void mutate("расчёт раздачи", () => settleRoom(view.room_id, token, view.version, route, routes));
  };
  const autoSettled = useRef<string|null>(null);
  useEffect(()=>{
    if(!view||!autoSettlementAllowed(view)||busy||pending)return;
    const key=`${view.room_id}:${view.game_id}:${view.version}`;
    if(autoSettled.current===key)return;
    const timer=setTimeout(()=>{
      if(inFlight.current||!autoSettlementAllowed(viewRef.current)||viewRef.current?.version!==view.version||activeRoomRef.current!==view.room_id)return;
      autoSettled.current=key;
      const token=newKey();
      void mutate("расчёт раздачи",()=>settleRoom(view.room_id,token,view.version,"pool",view.settlement_options!.passout_defaults));
    },1800);
    return()=>clearTimeout(timer);
  },[view,busy,pending,mutate]);
  const adjust = (value: { field: "pool" | "hill" | "vist"; seat: number;
    against: number | null; delta: number; reason: string }) => {
    if (!view) return;
    const token = newKey();
    void mutate("корректировка расчёта", () =>
      adjustRoom(view.room_id, token, view.version, value));
  };
  const chosenCards = useMemo(() => {
    const all = ownCards(view);
    return all.filter(card => selected.includes(cardId(card)));
  }, [view, selected]);
  const legal = useMemo(() => new Set((view?.legal_cards ?? []).map(cardId)), [view?.legal_cards]);
  const hand = orderHand(ownCards(view), order, sortMode);
  const isPlay = view?.phase === "opening_lead" || view?.phase === "play";
  const localPlay=view&&pendingPlay&&pendingPlay.room===view.room_id&&pendingPlay.game===view.game_id&&pendingPlay.version===view.version?pendingPlay:null;
  const canInteractCards = Boolean(!busy && !localPlay && view && allowedToAct(view) && (isPlay || view.phase === "discard"));
  const ownPlayable = canInteractCards && (!isPlay || view?.turn === view?.my_seat);
  const onCardSelect = (card: Card) => {
    const id = cardId(card);
    if (!canInteractCards || isPlay) return;
    setSelected(current => current.includes(id)
      ? current.filter(x => x !== id) : current.length < 2 ? [...current, id] : current);
  };
  const beginDrag=(e:DragEvent,kind:DragIntent["kind"],card?:Card,owner?:number)=>{
    if(!view||busy){e.preventDefault();return;}
    const scope={room:view.room_id,game:view.game_id,version:view.version};
    if(kind==="deck") dragging.current={kind,...scope};
    else if(card&&kind==="card"&&owner!==undefined) dragging.current={kind,...scope,id:cardId(card),owner};
    else if(card&&kind==="discard") dragging.current={kind,...scope,id:cardId(card)};
    else {e.preventDefault();return;}
    e.dataTransfer.setData("text/plain","preferans");e.dataTransfer.effectAllowed="move";
  };
  const endDrag=()=>{dragging.current=null;};
  const takeDrag=(e:DragEvent)=>{e.preventDefault();e.stopPropagation();const drag=dragging.current;dragging.current=null;return view&&!busy&&matchingDrag(drag,view)?drag:null;};
  const playNow=(card:Card,owner:number)=>{
    if(!view||busy||localPlay||inFlight.current||!isPlay||!allowedToAct(view)||view.turn!==owner||!legal.has(cardId(card)))return;
    setPendingPlay({room:view.room_id,game:view.game_id,version:view.version,owner,card});
    command("play",{card,owner});
  };
  const renderOpenCard = (card: Card, seat: Seat) => {
    const playable = Boolean(isPlay && canInteractCards && view?.turn === seat && legal.has(cardId(card)));
    return <CardFace card={card} playable={playable} pendingPlay={!!localPlay&&localPlay.owner===seat&&cardId(localPlay.card)===cardId(card)}
      onDragStart={isPlay&&!busy?e=>beginDrag(e,"card",card,seat):undefined} onDragEnd={endDrag}
      onKeyDown={e=>{if(playable&&(e.key==="Enter"||e.key===" ")){e.preventDefault();playNow(card,seat);}}}/>;
  };
  const reorder = (from:string,to:string) => {
    const ids=hand.map(cardId), a=ids.indexOf(from), b=ids.indexOf(to);
    if(a<0||b<0||a===b)return;
    ids.splice(a,1);ids.splice(b,0,from);setOrder(ids);
  };
  const tableDrop=(e:DragEvent)=>{
    const drag=takeDrag(e);if(!view||!drag)return;
    if(drag.kind==="deck"&&view.my_seat===dealerFor(view)&&mayStart(view)){start();return;}
    if(drag.kind!=="card")return;
    if(isPlay&&(view.controller!==view.my_seat||view.turn!==drag.owner)){setDropNotice("Убери карту, не твой ход!");return;}
    const card=legalDrop(view,drag);
    if(card&&view.turn!=null)playNow(card,view.turn);
    else if(isPlay)setDropNotice("Ты чё, слепой!? Правильно давай ходи!");
  };
  const seatDrop=(seat:Seat,e:DragEvent)=>{const drag=takeDrag(e);if(view&&drag?.kind==="deck"&&mayPassDeck(view,seat))command("dealer_pass",{dealer:seat});};
  const draft=Boolean(view?.phase==="discard"&&view.my_seat===view.declarer);
  const discardDrop=(e:DragEvent)=>{const drag=takeDrag(e);if(view&&draft&&canInteractCards&&drag?.kind==="card"&&drag.owner===view.my_seat&&hand.some(c=>cardId(c)===drag.id))setSelected(old=>changeDraft(old,drag.id,true));};
  const handDrop=(e:DragEvent,target?:string)=>{const drag=takeDrag(e);if(!view||!drag)return;if(drag.kind==="discard"&&draft&&canInteractCards)setSelected(old=>changeDraft(old,drag.id,false));else if(drag.kind==="card"&&drag.owner===view.my_seat&&target)reorder(drag.id,target);};
  const copyInvitation = () => {
    if (!roomId) return;
    void navigator.clipboard.writeText(window.location.href).then(() => setStatus("Ссылка скопирована."))
      .catch(() => setStatus("Не удалось скопировать. Скопируй адрес из браузера."));
  };

  const shared: SharedCommand = (action, args = {}) => {
    if (view?.presentation) command(action, { ...args, presentation_version: view.presentation.revision });
  };
  const openShared = (kind: OverlayKind) => shared("overlay_open", {kind});
  const visibleHand=draft?hand.filter(c=>!selected.includes(cardId(c))):hand;
  const settings=<div className={styles.settingsPanel}>
    <CycleSetting<SortMode> label="Сортировка карт" value={sortMode} options={[["grouped","По длине масти"],["suit","По порядку мастей"]]} onChange={changeSort}/>
    <button type="button" onClick={()=>setOrder([])}>Автосортировка</button>
    <CycleSetting<TableTheme|"room"> label="Игровое поле" value={localTableTheme==="glass"?"felt":localTableTheme} options={[["room","Как в комнате"],["felt","Зелёное сукно"],["blue","Синее сукно"],["wood","Тёплый коричневый"]]} onChange={changeTableTheme}/>
    <label className={styles.transparencySetting}>Прозрачность: {Math.round((1-opacity)*100)}% <input type="range" min={0} max={75} step={5} value={Math.round((1-opacity)*100)} onChange={e=>changeTransparency(Number(e.target.value))}/></label>
    {view?.room_admin&&["lobby","playing","between","awaiting_settlement"].includes(view.status)&&<CycleSetting<TableTheme> label="Поле комнаты по умолчанию" value={view.table_theme==="glass"?"felt":view.table_theme??"felt"} disabled={busy||Boolean(view.controls?.paused)} options={[["felt","Зелёное сукно"],["blue","Синее сукно"],["wood","Тёплый коричневый"]]} onChange={theme=>command("table_theme",{theme})}/>}
    <fieldset className={styles.backChoices}><legend>Рубашка карт</legend>{([["classic","Текущая классическая"],["ornament","Красный орнамент"],["red-blue","Красно-голубая сетка"],["green","Зелёная сетка"]] as const).map(([value,label])=><button type="button" key={value} aria-pressed={back===value} title={label} onClick={()=>changeBack(value)}><CardBackContext.Provider value={value}><CardArtwork decorative/></CardBackContext.Provider><span>{label}</span></button>)}</fieldset>
    {view&&[0,1,2].some(seat=>mayPassDeck(view,seat))&&<div><strong>Передать колоду</strong>{[0,1,2].filter(seat=>mayPassDeck(view,seat)).map(seat=><button key={seat} type="button" disabled={busy} onClick={()=>command("dealer_pass",{dealer:seat})}>{profiles?.[seat]?.name||seatNames[seat]}</button>)}</div>}
    <small>Для ручной сортировки клавиатурой: Alt + стрелка влево или вправо.</small>
  </div>;
  const ownHand = view && <div className={styles.handsPanel}>
    {draft&&<div className={styles.discardSlots} aria-label="Зона сноса" onDragOver={e=>e.preventDefault()} onDrop={discardDrop}>
      {[0,1].map(i=>{const card=chosenCards[i];return <button key={i} type="button" className={styles.discardSlot} data-pointer-drag="discard" aria-label={card?`Вернуть карту ${cardLabel(card)} в руку`:"Место для сноса"} disabled={!card||!canInteractCards} draggable={!!card&&canInteractCards} onDragStart={e=>card&&beginDrag(e,"discard",card)} onDragEnd={endDrag} onClick={()=>card&&setSelected(old=>changeDraft(old,cardId(card),false))}>{card?<CardArtwork card={peekDiscard?card:undefined}/>:"+"}</button>;})}
      <button type="button" aria-label="Посмотреть выбранный снос" aria-pressed={peekDiscard} onClick={()=>setPeekDiscard(v=>!v)}>◉</button>
    </div>}
    {!draft&&view.own_discard?.length===2&&<div className={styles.discardSlots} aria-label="Сброшенные карты">
      {view.own_discard.map((c,i)=><button type="button" className={styles.discardSlot} key={i} aria-label="Посмотреть свой снос" onClick={()=>view.presentation?.enabled?openShared("discard_replay"):setPeekDiscard(v=>!v)}><CardArtwork card={!view.presentation?.enabled&&peekDiscard?c:undefined}/></button>)}
    </div>}
    <div className={styles.handRow} aria-label="Игровые карты" onDragOver={e=>e.preventDefault()} onDrop={e=>handDrop(e)}>
      {visibleHand.map((card,index)=><div data-hand-card="true" data-suit-break={index>0&&visibleHand[index-1].suit!==card.suit?"true":undefined} data-from-widow={draft&&view.widow?.some(c=>cardId(c)===cardId(card))?"true":undefined} className={styles.cardWithSort} key={cardId(card)}>
        <CardFace card={card} selected={false} pendingPlay={!!localPlay&&localPlay.owner===view.my_seat&&cardId(localPlay.card)===cardId(card)} playable={ownPlayable&&(draft||legal.has(cardId(card)))}
          onClick={ownPlayable&&draft?()=>onCardSelect(card):undefined}
          onDragStart={e=>beginDrag(e,"card",card,view.my_seat??undefined)} onDragEnd={endDrag}
          onDragOver={e=>e.preventDefault()} onDrop={e=>handDrop(e,cardId(card))}
          onKeyDown={e=>{if(isPlay&&ownPlayable&&legal.has(cardId(card))&&(e.key==="Enter"||e.key===" ")){e.preventDefault();if(view.my_seat!=null)playNow(card,view.my_seat);return;}if(e.altKey&&(e.key==="ArrowLeft"||e.key==="ArrowRight")){const target=visibleHand[index+(e.key==="ArrowLeft"?-1:1)];if(target){e.preventDefault();reorder(cardId(card),cardId(target));}}}}/>
      </div>)}
      {!visibleHand.length&&<span className={styles.subtle}>Нет карт для отображения</span>}
    </div>
  </div>;
  const actions = view && <>
    {view.status === "lobby" && view.lobby_setup && <RulesetEditor view={view} busy={busy} command={command}/>}
    {view.status === "lobby" && view.lobby_setup && <><LobbySetup view={view} busy={busy} command={command} /><SeatSwap view={view} profiles={profiles} busy={busy} command={command}/></>}
    <ActionPanel view={view} busy={busy} selectedCards={chosenCards} profiles={profiles}
      command={command} regularRoute={regularRoute} setRegularRoute={setRegularRoute}
      onStart={start} onSettle={settle} />
  </>;
  return <CardBackContext.Provider value={back}><main className={`${styles.root} ${styles.tableRoot}`}>
    <header className={styles.header}>
      <div><p className={styles.eyebrow}>Частная игра · Преферанс по-запорожски</p><h1>Преферанс</h1>
</div>
      <div className={styles.headerTools}><div className={styles.headerStatus} data-offline={!online&&!rtReady?"true":undefined}><span className={online ? styles.statusDot : styles.statusOff} aria-hidden="true" />
        {rtReady ? "Обновление в реальном времени" : online ? "Резервная связь" : "Переподключение"}</div></div>
    </header>

    <div className={styles.tableShell}>
        {!roomId && <><Lobby openRoom={openRoom} create={create} busy={busy}/><PreferansHistory/></>}

        {roomId && !view && <section className={styles.roomBar} aria-label="Комната">
          <div><strong>Комната</strong> <code>{roomId.slice(0, 8)}…{roomId.slice(-6)}</code><span className={styles.subtle}>{invited ? "Приглашение" : "Подключение…"}</span></div>
          <div className={styles.actions}>
            <button type="button" onClick={copyInvitation}>Скопировать приглашение</button>
            <button type="button" onClick={leaveRoom}>К выбору комнаты</button>
          </div>
        </section>}

        {roomId && invited && !view && <section className={styles.panel}>
          <h2>Приглашение найдено</h2>
          <p>В комнате {invited.occupied.filter(Boolean).length} из 3 участников. После входа ты займёшь свободное место.</p>
          <button type="button" className={styles.primary} disabled={busy || invited.occupied.every(Boolean)} onClick={join}>Занять место</button>
        </section>}

        {view && <>
          <ImmersiveMenu key={view.room_id} active={view.status !== "lobby"} settings={settings} copy={copyInvitation} leave={leaveRoom}
            controls={<><PreferansControls view={view} busy={busy} command={command} adjust={adjust}/><ReleaseControls key={`${view.room_id}:${view.game_id}`} view={view} busy={busy} command={command}/></>}
            urgent={Boolean(view.reveal || view.controls?.counter || view.controls?.undo || view.punch_choices?.some(pair=>pair.to===view.my_seat&&pair.replacement===null))}
            shared={view.presentation?.enabled ? openShared : undefined}
            media={LIVE_MEDIA_ENABLED && !archived && view.my_seat !== null
              ? <LiveMediaControls media={liveMedia}/> : <p>Видео и голос пока отключены. Игровая связь от них не зависит.</p>}>
            <GameTable view={view} profiles={profiles} presence={rtReady&&rtPresence?rtPresence:null} localConnected={online||rtReady}
              theme={selectedTheme} surfaceOpacity={opacity} sheetExit={<SheetExit view={view} busy={busy} command={command}/>} serverNow={serverNow} pendingPlay={localPlay} sortMode={sortMode} busy={busy} onReplay={view.presentation?.enabled?()=>openShared("last_trick"):undefined}
              statusLine={`${dropNotice||status|| (view.controls?.paused?"Пауза":statusNames[view.status])} · ${phaseLabel(view.phase)}${isPlay&&view.turn!=null?` · Ход: ${profiles?.[view.turn]?.name||seatNames[view.turn]}`:""}${isPlay&&view.turn!==view.my_seat&&view.controller===view.my_seat?" · Управляешь открытой рукой":""}`}
              announcement={view.status==="closed"&&view.sheet_loser!==undefined?<div className={styles.sheetDrama} role="alert">{profiles?.[view.sheet_loser]?.name||seatNames[view.sheet_loser]}: ПСИХАНУЛ и выкинул листик. По голому удару ему!</div>:view.end_reason==="without_three"&&view.declarer!=null&&view.my_seat!==null&&view.my_seat!==view.declarer&&["awaiting_settlement","between"].includes(view.status)?<p className={styles.concedeDrama} role="status">{profiles?.[view.declarer]?.name||seatNames[view.declarer]} зассал и кинул «без трёх»!</p>:undefined}
              hand={ownHand} actions={actions} renderOpenCard={renderOpenCard} onTableDrop={tableDrop} onSeatDrop={seatDrop}
              deck={dealerFor(view)!==null?<Deck enabled={!busy&&view.my_seat===dealerFor(view)&&(mayStart(view)||[0,1,2].some(seat=>mayPassDeck(view,seat)))} canDeal={mayStart(view)} start={start} drag={e=>beginDrag(e,"deck")} end={endDrag}/>:undefined}
              localControls={LIVE_MEDIA_ENABLED&&!archived&&view.my_seat!==null?<div className={styles.ownMediaButtons}>{!liveMedia.state.joined?<button type="button" disabled={!liveMedia.available||liveMedia.state.joining} onClick={liveMedia.join} title="Вход в звонок с выключенными камерой и микрофоном">Связь</button>:<><button type="button" aria-label={liveMedia.state.audio?"Выключить микрофон":"Включить микрофон"} aria-pressed={liveMedia.state.audio} disabled={liveMedia.state.changing} title={liveMedia.state.audio?"Выключить микрофон":"Включить микрофон"} onClick={()=>liveMedia.toggle("audio")}>{liveMedia.state.audio?"🎙":"🔇"}</button><button type="button" aria-label={liveMedia.state.video?"Выключить камеру":"Включить камеру"} aria-pressed={liveMedia.state.video} disabled={liveMedia.state.changing} title={liveMedia.state.video?"Выключить камеру":"Включить камеру"} onClick={()=>liveMedia.toggle("video")}>{liveMedia.state.video?"▣":"⊘"}</button><button type="button" aria-label="Выйти из звонка" onClick={liveMedia.leave}>×</button></>}</div>:undefined}
              mediaForSeat={LIVE_MEDIA_ENABLED && !archived && rtReady && view.my_seat !== null && liveMedia.state.joined ? seat => <MediaSeatTile media={liveMedia} seat={seat} own={seat===view.my_seat}/> : undefined}
              onScore={view.presentation?.enabled?()=>openShared("score_sheet"):undefined}
              objects={view.presentation?.enabled ? <SharedObjects busy={busy} open={openShared}/> : undefined}
              onField={view.presentation?.overlay ? () => shared("overlay_close", {overlay_id: view.presentation?.overlay?.id}) : undefined}
              sharedPanel={view.presentation && <SharedRoom key={view.room_id} view={view} profiles={profiles} busy={busy} command={shared} serverNow={serverNow} sheetExit={<SheetExit view={view} busy={busy} command={command}/>}/>}/>
          </ImmersiveMenu>
        </>}
    </div>
    {((!view&&status) || (!busy&&pending) || (busy&&pending?.label!=="play")) && <div className={styles.notification} role="status" aria-live="polite">
      {busy ? "Операция выполняется…" : status}
      {!busy && pending && <button type="button" onClick={() => void mutate(pending.label, pending.run)}>Повторить операцию</button>}
    </div>}
  </main></CardBackContext.Provider>;
}
