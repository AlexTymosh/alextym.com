"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DragEvent } from "react";
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
import { ScoreAdjustment } from "./ScoreAdjustment.ru";
import { LiveMediaControls, MediaSeatTile, useLiveMedia } from "./LiveMedia.ru";
import { connectRealtime, type Presence } from "./realtime-client";
import { canHint, sharedHint, hintKey, hintScope, canRaiseOwn, ownRaiseScope, mergeHintSnapshot, type HintSender } from "./defense-hints";
import { pauseMessage, awardedMessage, auctionMessage, illegalCardMessage, declarationMessage } from "./play-status.ru";
import { CounterDisplay } from "./CounterDisplay.ru";
import { useDiscardScene } from "./HiddenDiscardScene.ru";
import { gagPhase } from "./gag-model";
import { CardArtwork } from "./CardArtwork.ru";
import { EyeIcon, UndoIcon } from "./GameIcons";
import { GameTable } from "./GameTable.ru";
import { SharedRoom, SharedObjects, type SharedCommand } from "./SharedRoom.ru";
import { replayMoveAllowed, type OverlayKind } from "./presentation-model";
import { ProjectSidebar as ImmersiveMenu } from "./ProjectSidebar.ru";
import { RoomReturn } from "./RoomReturn.ru";
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
import { ClaimPanel } from "./ClaimPanel.ru";
import { ByOwnButton } from "./ByOwnButton.ru";
import { lobbyReady } from "./room-preparation";
import { UndoRequest, ControlFeedback, TableZoom } from "./ControlDialogs.ru";
import { canRequestUndo, tableZoomValue } from "./control-feedback";
import { MisereOfferPanel } from "./MisereOfferPanel.ru";
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

function CardFace({ card, selected, playable, pendingPlay, fromWidow, raised, onHint, onClick, onDoubleClick, onDragStart, onDragOver, onDrop, onDragEnd, onKeyDown }: {
  card: Card; selected?: boolean; playable?: boolean; pendingPlay?:boolean; fromWidow?:boolean; onClick?: () => void; onDoubleClick?:()=>void;
  raised?:boolean; onHint?:()=>void;
  onDragStart?: (event: DragEvent<HTMLButtonElement>) => void;
  onDragOver?: (event: DragEvent<HTMLButtonElement>) => void;
  onDrop?: (event: DragEvent<HTMLButtonElement>) => void;
  onDragEnd?: ()=>void;
  onKeyDown?: (event: import("react").KeyboardEvent<HTMLButtonElement>)=>void;
}) {
  const red = card.suit === "D" || card.suit === "H";
  const clickTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const cancelHint=()=>{if(clickTimer.current!==null)clearTimeout(clickTimer.current);clickTimer.current=null;};
  useEffect(()=>()=>{if(clickTimer.current!==null)clearTimeout(clickTimer.current);},[]);
  return (
    <button type="button" className={`${styles.playingCard} ${red ? styles.red : ""} ${selected ? styles.selected : ""} ${playable ? styles.playable : ""}`}
      aria-label={`${cardLabel(card)}${selected ? ", выбрана" : ""}${fromWidow?", прикуп":""}`}
      aria-pressed={Boolean(selected||raised)} disabled={!onClick && !onHint && !onDragStart && !onDoubleClick} data-defense-raised={raised?"true":undefined} data-defense-hintable={onHint?"true":undefined}
      onClick={onHint?e=>{cancelHint();if(e.detail<2)clickTimer.current=setTimeout(()=>{clickTimer.current=null;onHint();},350);}:onClick}
      onDoubleClick={onDoubleClick?()=>{cancelHint();onDoubleClick();}:undefined}
      draggable={Boolean(onDragStart)} onDragStart={onDragStart?e=>{cancelHint();onDragStart(e);}:undefined} onDragOver={onDragOver} onDrop={onDrop} onDragEnd={onDragEnd} onKeyDown={onKeyDown}
      data-card={cardId(card)} data-pending-play={pendingPlay?"true":undefined}>
      <CardArtwork card={card} decorative />
      {fromWidow&&<span className={styles.widowLabel} aria-hidden="true">прикуп</span>}
    </button>
  );
}

function ActionPanel({ view, busy, command, profiles,
  regularRoute, setRegularRoute, onStart, onSettle }: {
  view: RoomView; busy: boolean; profiles:SeatProfile[]|null;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
  regularRoute: "pool" | "hill_first"; setRegularRoute: (x: "pool" | "hill_first") => void;
  onStart: () => void; onSettle: () => void;
}) {
  const myTurn = allowedToAct(view);
  if(view.claim?.status==="pending")return null;
  if (view.status === "playing" && (view.controls?.undo || (view.controls?.paused && !replayMoveAllowed(view)))) {
    return null;
  }
  if (view.status === "between" && view.next_deal && REALTIME_ENABLED) return null;
  if (view.status === "between") return null;
  if (view.status === "lobby") {
    if(!lobbyReady(view))return null;
    return view.my_seat===dealerFor(view)?<button type="button" className={styles.primary} disabled={busy||!mayStart(view)} onClick={onStart}>Раздать карты</button>:<small>Ожидаем первую раздачу</small>;
  }
  if (view.final_review) return null;
  if (view.status === "awaiting_settlement") {
    const choices=view.settlement_options;
    const waiting=choices?.passout_pending??[];
    if(waiting.length){
      const name=(seat:number)=>profiles?.[seat]?.name||seatNames[seat];
      const mine=view.my_seat!==null&&waiting.includes(view.my_seat)?view.my_seat:null;
      const targets=mine===null?[]:choices?.passout_targets?.[mine]??[];
      return <section className={styles.actionPanel} aria-label="Бонус распасов">
        {mine!==null?<div className={styles.actions}>{choices?.passout_choices?.[mine]?.map(route=><button type="button" key={route} disabled={busy||!!view.controls?.paused} onClick={()=>command("passout_reward",{route})}>{route==="hill_first"?"Списать с горы":route==="pool"?"Записать себе в пулю":targets.length?`Написать ${targets.length>1?"поровну ":""}на ${targets.map(name).join(" и ")}`:"Расписать висты поровну"}</button>)}</div>:null}
      </section>;
    }
    if(view.settlement_options?.regular_choice===false)return null;
    if(!view.settlement_options)return view.room_admin?<button type="button" className={styles.primary} disabled={busy||Boolean(view.controls?.paused||view.controls?.undo)} onClick={onSettle}>Рассчитать раздачу</button>:null;
    return <section className={styles.actionPanel} aria-label="Сдача завершена">
      {view.my_seat===view.declarer ? <>
        {view.settlement_options?.regular_choice && <div className={styles.rewardRoute} role="group" aria-label="Куда записать выигрыш">
          <strong>Куда записать выигрыш</strong><div>
            <button type="button" disabled={busy||Boolean(view.controls?.paused||view.controls?.undo)} aria-pressed={regularRoute==="pool"} onClick={()=>setRegularRoute("pool")}>Записать соперникам в пулю</button>
            <button type="button" disabled={busy||Boolean(view.controls?.paused||view.controls?.undo)} aria-pressed={regularRoute==="hill_first"} onClick={()=>setRegularRoute("hill_first")}>Списать с горы</button>
          </div></div>}
        <button type="button" disabled={busy || Boolean(view.controls?.paused || view.controls?.undo)} className={styles.primary} onClick={onSettle}>Рассчитать раздачу</button>
      </> : null}
    </section>;
  }
  if (view.status === "archived" || view.status === "closed") return null;
  if (view.phase === "misere_offer") return null;
  if (!myTurn || view.phase === "play" || view.phase === "opening_lead" || view.phase === "discard") return null;
  return <section className={`${styles.actionPanel} ${styles.compactAction}`} aria-label="Игровое действие">
    {view.phase === "auction" && <>
      <BidPanel key={`${view.game_id}:auction`} view={view} busy={busy} command={command}/>
    </>}
    {view.phase === "declare" && <>
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
      <div className={styles.actions}>
        <button type="button" className={styles.primary} disabled={busy} onClick={() => command("mode", { mode: "open" })}>В светлую</button>
        <button type="button" disabled={busy} onClick={() => command("mode", { mode: "closed" })}>В тёмную</button>
      </div>
    </>}
  </section>;
}

export function PreferansGame({preferenceScope}: {preferenceScope?: string} = {}) {
  const [roomId, setRoomId] = useState("");
  const [historyOpen,setHistoryOpen]=useState(false);
  const [undoDraft,setUndoDraft]=useState<string|null>(null);
  const [tableZoom,setTableZoom]=useState(100);
  const zoomKey=preferenceScope?`preferans:table-zoom:${preferenceScope}`:null;
  useEffect(()=>{if(zoomKey)try{setTableZoom(tableZoomValue(localStorage.getItem(zoomKey)));}catch{/* Optional preference. */}},[zoomKey]);
  const changeTableZoom=(value:number)=>{const next=tableZoomValue(value);setTableZoom(next);if(zoomKey)try{localStorage.setItem(zoomKey,String(next));}catch{/* Optional preference. */}};
  const liveMedia = useLiveMedia();
  const {bind: bindMedia, receive: receiveMedia} = liveMedia;
  const [view, setView] = useState<RoomView | null>(null);
  const hintSender=useRef<{room:string;send:HintSender}|null>(null);
  const [localHints,setLocalHints]=useState<{scope:string;keys:string[]}>({scope:"",keys:[]});
  const [ownRaised,setOwnRaised]=useState<{scope:string;keys:string[]}>({scope:"",keys:[]});
  const [invited, setInvited] = useState<RoomInvitation | null>(null);
  const viewRef = useRef<RoomView | null>(null);
  const serverOffset = useRef(0);
  const serverNow = useCallback(() => Date.now() + serverOffset.current, []);
  const discardScene=useDiscardScene(view,serverNow);
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
  const autoJoinedRoom = useRef("");
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
  const surfaceKey=preferenceScope?`preferans:surface:${preferenceScope}`:null;
  const [surface,setSurface]=useState<"pine"|"cloth"|"plastic"|"green"|"blue"|"glass"|"walnut"|"marble"|"leather">("pine");
  const [tableTransparency,setTableTransparency]=useState(0);
  useEffect(()=>{if(surfaceKey)try{const raw=localStorage.getItem(surfaceKey);if(raw==="pine"||raw==="cloth"||raw==="plastic"||raw==="green"||raw==="blue"||raw==="glass"||raw==="walnut"||raw==="marble"||raw==="leather")setSurface(raw);else setSurface("pine");setTableTransparency(parseTransparency(localStorage.getItem(surfaceKey+":opacity"))??0);}catch{/* Optional preference. */}},[surfaceKey]);
  const roundKey=preferenceScope?`preferans:round-table:${preferenceScope}`:null;
  const [roundTable,setRoundTable]=useState(true);
  useEffect(()=>{if(roundKey)try{setRoundTable(localStorage.getItem(roundKey)!=="off");}catch{/* Optional preference. */}},[roundKey]);
  const changeRoundTable=(value:boolean)=>{setRoundTable(value);if(roundKey)try{localStorage.setItem(roundKey,value?"on":"off");}catch{/* Optional preference. */}};
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
    if(next.server_clock_ms!==undefined&&!next.presentation)serverOffset.current=next.server_clock_ms-Date.now();
    const before=viewRef.current;
    if(before?.game_id!==next.game_id||before?.phase!==next.phase||(before?.played_tricks??0)!==(next.played_tricks??0)||(before?.trick?.length??0)!==(next.trick?.length??0))setPeekDiscard(false);
    const merged=mergeHintSnapshot(viewRef.current,next,hintSender.current?.room===next.room_id);
    viewRef.current = merged;
    setView(merged);
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
    autoJoinedRoom.current = "";
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
    autoJoinedRoom.current = "";
    setProfileState(null);
    setHistoryOpen(false);setRoomId(""); setView(null); setInvited(null); setSelected([]); setStatus("");
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
            if (!stopped && activeRoomRef.current===roomId) {
              setInvited(found); setOnline(true); setStatus(""); errors = 0;
              if (!found.occupied.every(Boolean) && autoJoinedRoom.current!==roomId && !inFlight.current) {
                autoJoinedRoom.current=roomId;
                inFlight.current=true;setBusy(true);
                try {
                  await joinRoom(roomId,newKey(),found.version);
                  if(!stopped&&activeRoomRef.current===roomId){
                    const joined=await roomView(roomId);
                    if(!stopped&&activeRoomRef.current===roomId&&!("unchanged" in joined)){
                      if(joined.presentation)serverOffset.current=joined.presentation.server_now_ms-Date.now();
                      updateView(joined);setInvited(null);
                    }
                  }
                } finally {inFlight.current=false;setBusy(false);}
              }
            }
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
      onHintTransport: sender=>{if(activeRoomRef.current===roomId)hintSender.current=sender?{room:roomId,send:sender}:null;},
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
    if (!view || (action!=="sheet_discard"&&action!=="archive"&&gagPhase(view.redeal_gag,serverNow()))) return;
    const token = newKey();
    void mutate(action, () => sendCommand(view.room_id, token, view.version, action, args));
  };
  const settle = () => {
    if (!view) return;
    const token = newKey();
    if(view.settlement_options?.passout_pending?.length)return;
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
  const canInteractCards = Boolean(!busy && !discardScene.phase && !localPlay && view && allowedToAct(view) && (isPlay || view.phase === "discard"));
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
    if(!view||busy||localPlay||inFlight.current||!isPlay||!allowedToAct(view)||view.turn!==owner)return;
    if(!legal.has(cardId(card))){setDropNotice(illegalCardMessage(view));return;}
    setDropNotice("");
    setPendingPlay({room:view.room_id,game:view.game_id,version:view.version,owner,card});
    command("play",{card,owner});
  };
  const raised=(card:Card,owner:number)=>{
    if(!view)return false;
    const key=hintKey(owner,card);
    if(rtReady&&sharedHint(view,owner,card))return view.defense_hints?.some(mark=>hintKey(mark.owner,mark.card)===key)===true;
    return Boolean(canHint(view,owner,card)&&localHints.scope===hintScope(view)&&localHints.keys.includes(key)||
      canRaiseOwn(view,owner,card)&&ownRaised.scope===ownRaiseScope(view)&&ownRaised.keys.includes(key));
  };
  const toggleHint=(card:Card,owner:number)=>{
    // A delayed single click must not act on a newer deal or turn.
    if(!view||viewRef.current?.version!==view.version||viewRef.current?.game_id!==view.game_id||viewRef.current?.room_id!==view.room_id||!canHint(view,owner,card))return;
    const key=hintKey(owner,card),scope=hintScope(view);
    if(view.game_id&&sharedHint(view,owner,card)&&hintSender.current?.room===view.room_id&&hintSender.current.send({game_id:view.game_id,version:view.version,owner,card,raised:!raised(card,owner)})){
      setLocalHints(old=>old.scope===scope?{scope,keys:old.keys.filter(k=>k!==key)}:old);
      return;
    }
    setLocalHints(old=>{const keys=old.scope===scope?old.keys:[];return {scope,keys:keys.includes(key)?keys.filter(k=>k!==key):[...keys,key]};});
  };
  const toggleOwnRaise=(card:Card,owner:number)=>{
    const current=viewRef.current;
    if(!view||!current||ownRaiseScope(current)!==ownRaiseScope(view)||!canRaiseOwn(current,owner,card))return;
    const key=hintKey(owner,card),scope=ownRaiseScope(current);
    // Only the pre-existing authorization path can send an already-visible hint.
    if(sharedHint(current,owner,card)&&current.version===view.version&&current.game_id&&hintSender.current?.room===current.room_id&&hintSender.current.send({game_id:current.game_id,version:current.version,owner,card,raised:!raised(card,owner)})){
      setOwnRaised(old=>old.scope===scope?{scope,keys:old.keys.filter(k=>k!==key)}:old);
      return;
    }
    setOwnRaised(old=>{const keys=old.scope===scope?old.keys:[];return {scope,keys:keys.includes(key)?keys.filter(k=>k!==key):[...keys,key]};});
  };
  const renderOpenCard = (card: Card, seat: Seat) => {
    const playable = Boolean(isPlay && canInteractCards && view?.turn === seat && legal.has(cardId(card)));
    return <CardFace card={card} playable={playable} raised={raised(card,seat)} onHint={view&&canHint(view,seat,card)?()=>toggleHint(card,seat):undefined} pendingPlay={!!localPlay&&localPlay.owner===seat&&cardId(localPlay.card)===cardId(card)}
      onDragStart={isPlay&&!busy?e=>beginDrag(e,"card",card,seat):undefined} onDragEnd={endDrag}
      onDoubleClick={isPlay&&canInteractCards&&view?.turn===seat?()=>playNow(card,seat):undefined}
      onKeyDown={e=>{if(isPlay&&canInteractCards&&view?.turn===seat&&(e.key==="Enter"||e.key===" ")){e.preventDefault();playNow(card,seat);}}}/>;
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
    else if(isPlay&&allowedToAct(view)&&!localPlay&&!inFlight.current)setDropNotice(illegalCardMessage(view));
  };
  const seatDrop=(seat:Seat,e:DragEvent)=>{const drag=takeDrag(e);if(view&&drag?.kind==="deck"&&mayPassDeck(view,seat))command("dealer_pass",{dealer:seat});};
  const draft=Boolean(view?.phase==="discard"&&view.my_seat===view.declarer);
  const discardDrop=(e:DragEvent)=>{const drag=takeDrag(e);if(view&&draft&&canInteractCards&&drag?.kind==="card"&&drag.owner===view.my_seat&&hand.some(c=>cardId(c)===drag.id))setSelected(old=>changeDraft(old,drag.id,true));};
  const handDrop=(e:DragEvent,target?:string)=>{const drag=takeDrag(e);if(!view||!drag)return;if(drag.kind==="discard"&&draft&&canInteractCards)setSelected(old=>changeDraft(old,drag.id,false));else if(drag.kind==="card"&&drag.owner===view.my_seat&&target)reorder(drag.id,target);};
  const copyInvitation = () => {
    if (!roomId) return;
    const url=new URL("/portfolio/preferans",window.location.origin);
    url.searchParams.set("room",roomId);
    if(!navigator.clipboard){setStatus("Не удалось скопировать. Скопируй адрес из браузера.");return;}
    void navigator.clipboard.writeText(url.href).then(() => setStatus("Ссылка скопирована."))
      .catch(() => setStatus("Не удалось скопировать. Скопируй адрес из браузера."));
  };

  const shared: SharedCommand = (action, args = {}) => {
    if (view?.presentation) command(action, { ...args, presentation_version: view.presentation.revision });
  };
  const openShared = (kind: OverlayKind) => shared("overlay_open", {kind});
  const visibleHand=draft?hand.filter(c=>!selected.includes(cardId(c))):hand;
  const settings=<div className={styles.settingsPanel}>
    {view&&<>{view.status==="lobby"&&<><LobbySetup view={view} profiles={profiles} busy={busy} command={command} mode="config"/><RulesetEditor view={view} busy={busy} command={command}/><PreferansControls view={view} profiles={profiles} busy={busy} command={command}/></>}<ReleaseControls key={`${view.room_id}:${view.game_id}`} view={view} busy={busy} command={command}/></>}
    <CycleSetting<SortMode> label="Сортировка карт" value={sortMode} options={[["grouped","По длине масти"],["suit","По порядку мастей"]]} onChange={changeSort}/>
    <button type="button" onClick={()=>setOrder([])}>Автосортировка</button>
    <CycleSetting<TableTheme|"room"> label="Игровое поле" value={localTableTheme==="glass"?"felt":localTableTheme} options={[["room","Как в комнате"],["felt","Зелёное сукно"],["blue","Синее сукно"],["wood","Тёплый коричневый"]]} onChange={changeTableTheme}/>
    <label><input type="checkbox" checked={roundTable} onChange={e=>changeRoundTable(e.target.checked)}/> Круглый стол (вид сверху)</label>
    <CycleSetting<typeof surface> label="Поверхность круглого стола" value={surface} options={[["pine","Сосна"],["cloth","Скатерть"],["plastic","Советский пластик"],["green","Зелёная"],["blue","Синяя"],["glass","Стекло"],["walnut","Тёмный орех"],["marble","Мрамор"],["leather","Тёмная кожа"]]} onChange={value=>{setSurface(value);if(surfaceKey)try{localStorage.setItem(surfaceKey,value);}catch{/* Optional preference. */}}}/>
    <label>Прозрачность стола: {tableTransparency}% <input type="range" min={0} max={75} step={5} value={tableTransparency} onChange={e=>{const value=Number(e.target.value);setTableTransparency(value);if(surfaceKey)try{localStorage.setItem(surfaceKey+":opacity",String(value));}catch{/* Optional preference. */}}}/></label>
    <label className={styles.transparencySetting}>Прозрачность поля: {Math.round((1-opacity)*100)}% <input type="range" min={0} max={75} step={5} value={Math.round((1-opacity)*100)} onChange={e=>changeTransparency(Number(e.target.value))}/></label>
    {view?.room_admin&&["lobby","playing","between","awaiting_settlement"].includes(view.status)&&<CycleSetting<TableTheme> label="Поле комнаты по умолчанию" value={view.table_theme==="glass"?"felt":view.table_theme??"felt"} disabled={busy||Boolean(view.controls?.paused)} options={[["felt","Зелёное сукно"],["blue","Синее сукно"],["wood","Тёплый коричневый"]]} onChange={theme=>command("table_theme",{theme})}/>}
    <fieldset className={styles.backChoices}><legend>Рубашка карт</legend>{([["classic","Текущая классическая"],["ornament","Красный орнамент"],["red-blue","Красно-голубая сетка"],["green","Зелёная сетка"]] as const).map(([value,label])=><button type="button" key={value} aria-pressed={back===value} title={label} onClick={()=>changeBack(value)}><CardBackContext.Provider value={value}><CardArtwork decorative/></CardBackContext.Provider><span>{label}</span></button>)}</fieldset>
    {view&&[0,1,2].some(seat=>mayPassDeck(view,seat))&&<div><strong>Передать колоду</strong>{[0,1,2].filter(seat=>mayPassDeck(view,seat)).map(seat=><button key={seat} type="button" disabled={busy} onClick={()=>command("dealer_pass",{dealer:seat})}>{profiles?.[seat]?.name||seatNames[seat]}</button>)}</div>}
    <small>Для ручной сортировки клавиатурой: Alt + стрелка влево или вправо.</small>
  </div>;
  const ownReview=view?.presentation?.overlay;
  const sharedDiscard=ownReview?.kind==="discard_replay"&&ownReview.seat===view?.my_seat;
  const discardVisible=Boolean(view?.presentation?.enabled?sharedDiscard:peekDiscard);
  const toggleDiscardReview=()=>{
    if(view?.presentation?.enabled){
      if(sharedDiscard&&ownReview)shared("overlay_close",{overlay_id:ownReview.id});
      else openShared("discard_replay");
    }else setPeekDiscard(v=>!v);
  };
  const declareBesideDiscard=Boolean(view&&view.phase==="declare"&&view.my_seat===view.declarer&&view.own_discard?.length===2);
  const ownHand = view && <div className={styles.handsPanel}>
    {draft&&<div className={styles.discardSlots} aria-label="Зона сноса" onDragOver={e=>e.preventDefault()} onDrop={discardDrop}>
      {[0,1].map(i=>{const card=chosenCards[i];return <button key={i} type="button" className={styles.discardSlot} data-pointer-drag="discard" aria-label={card?`Вернуть карту ${cardLabel(card)} в руку`:"Место для сноса"} disabled={!card||!canInteractCards} draggable={!!card&&canInteractCards} onDragStart={e=>card&&beginDrag(e,"discard",card)} onDragEnd={endDrag} onClick={()=>card&&setSelected(old=>changeDraft(old,cardId(card),false))}>{card?<CardArtwork card={peekDiscard?card:undefined}/>:"+"}</button>;})}
      <div className={styles.discardActions}>
        <button type="button" aria-label="Посмотреть выбранный снос" aria-pressed={peekDiscard} onClick={()=>setPeekDiscard(v=>!v)}><EyeIcon/></button>
        <button type="button" className={styles.primary} disabled={!canInteractCards||chosenCards.length!==2} onClick={()=>command("discard",{cards:chosenCards})}>Снести две карты</button>
        <button type="button" disabled={!canInteractCards||chosenCards.length!==2} onClick={()=>command("discard",{cards:chosenCards,hide_under_sheet:true})}>Спрятать надежно</button>
      </div>
    </div>}
    {!draft&&view.my_seat===view.declarer&&view.own_discard?.length===2&&<div className={styles.declareRow} data-declaration={declareBesideDiscard?"true":undefined}>
      {declareBesideDiscard&&<div className={styles.declareBids} data-table-actions="true"><ActionPanel view={view} busy={busy||!!discardScene.phase} profiles={profiles} command={command} regularRoute={regularRoute} setRegularRoute={setRegularRoute} onStart={start} onSettle={settle}/></div>}
      <div className={styles.discardReview}>
        {discardVisible&&<small className={styles.discardReviewNote} role="status">{view.presentation?.enabled?"Соперники видят, что вы подглядываете, но не видят сами сброшенные карты":"Сброшенные карты видишь только ты"}</small>}
        <div className={styles.discardSlots} aria-label={view.hidden_discard?"Спрятанный снос":"Сброшенные карты"}>
          {view.own_discard.map((card,i)=><span className={styles.discardSlot} key={i}><CardArtwork card={discardVisible?card:undefined}/></span>)}
          <button type="button" disabled={busy||!!discardScene.phase||view.claim?.status==="pending"} aria-label={discardVisible?"Скрыть снос":"Показать снос"} aria-pressed={discardVisible} onClick={toggleDiscardReview}><EyeIcon/></button>
        </div>
      </div>
    </div>}
    <div className={styles.handRow} aria-label="Игровые карты" onDragOver={e=>e.preventDefault()} onDrop={e=>handDrop(e)}>
      {visibleHand.map((card,index)=><div data-hand-card="true" data-suit-break={index>0&&visibleHand[index-1].suit!==card.suit?"true":undefined} data-from-widow={draft&&view.widow?.some(c=>cardId(c)===cardId(card))?"true":undefined} className={styles.cardWithSort} key={cardId(card)}>
        <CardFace card={card} selected={false} raised={view.my_seat!==null&&raised(card,view.my_seat)} onHint={!busy&&!discardScene.phase&&view.my_seat!==null&&canRaiseOwn(view,view.my_seat,card)?()=>toggleOwnRaise(card,view.my_seat!):undefined} fromWidow={draft&&view.widow?.some(c=>cardId(c)===cardId(card))} pendingPlay={!!localPlay&&localPlay.owner===view.my_seat&&cardId(localPlay.card)===cardId(card)} playable={ownPlayable&&(draft||legal.has(cardId(card)))}
          onClick={ownPlayable&&draft?()=>onCardSelect(card):undefined}
          onDoubleClick={isPlay&&ownPlayable?()=>{if(view.my_seat!==null)playNow(card,view.my_seat);}:undefined}
          onDragStart={e=>beginDrag(e,"card",card,view.my_seat??undefined)} onDragEnd={endDrag}
          onDragOver={e=>e.preventDefault()} onDrop={e=>handDrop(e,cardId(card))}
          onKeyDown={e=>{if(e.altKey&&e.key==="ArrowUp"&&view.my_seat!==null&&canRaiseOwn(view,view.my_seat,card)){e.preventDefault();toggleOwnRaise(card,view.my_seat);return;}if(isPlay&&ownPlayable&&(e.key==="Enter"||e.key===" ")){e.preventDefault();if(view.my_seat!=null)playNow(card,view.my_seat);return;}if(e.altKey&&(e.key==="ArrowLeft"||e.key==="ArrowRight")){const target=visibleHand[index+(e.key==="ArrowLeft"?-1:1)];if(target){e.preventDefault();reorder(cardId(card),cardId(target));}}}}/>
      </div>)}
      {!visibleHand.length&&view.status==="playing"&&<span className={styles.subtle}>Нет карт для отображения</span>}
    </div>
  </div>;
  const playerName=(seat:number)=>profiles?.[seat]?.name||seatNames[seat]||"Игрок";
  const undoScope=view?`${view.room_id}:${view.game_id}:${view.controls?.undo_candidate_version??view.version}`:"";
  const undoAllowed=Boolean(view&&canRequestUndo(view)&&!discardScene.phase);
  const tableStatus = view && (()=>{
    const transient=dropNotice||status||(busy&&pending?.label!=="play"?"Операция выполняется…":"");
    if(view.controls?.counter&&!view.controls?.undo)return <>{transient&&<small>{transient}</small>}<CounterDisplay view={view} name={playerName} serverNow={serverNow} busy={busy} onCancel={()=>command("counter_cancel")}/></>;
    if(transient&&!view.controls?.undo)return transient;
    if(view.final_review)return "Проверьте итоговые расчёты";
    if(view.status==="closed")return "Закончили!";
    if(view.status==="archived")return "Партия архивирована";
    if(view.controls?.undo)return "Голосование за отмену";
    if(view.controls?.paused)return pauseMessage(view,rtPresence,playerName);
    if(discardScene.phase)return "Пересдаём!";
    if(view.claim?.status==="rejected")return `${playerName(view.claim.rejected_by!)} не согласен`;
    if(view.status==="lobby")return lobbyReady(view)?"Все готовы!":`Сбор игроков · ${view.occupied.filter(Boolean).length} из 3`;
    if(view.status==="between")return <>{awardedMessage(view,playerName)}{view.next_deal&&REALTIME_ENABLED?<DealStatus view={view}/>:"Новая раздача"}</>;
    if(view.status==="awaiting_settlement"){
      const waiting=view.settlement_options?.passout_pending??[];
      return <>{awardedMessage(view,playerName)}<span>{waiting.length?`${waiting.map(playerName).join(", ")} ${waiting.length===1?"решает":"решают"} куда записать выигрыш`:view.settlement_options?.regular_choice?`${playerName(view.declarer??0)} решает куда записать — снять с горы или записать соперникам в пулю`:"Подсчёт результатов"}</span></>;
    }
    if(view.phase==="misere_offer")return `Мизер · ждём согласия ${view.misere_offer?.approved.length??0}/2`;
    if(view.phase==="discard"&&view.my_seat===view.declarer)return "Перетащи две карты в снос";
    if(view.phase==="declare")return declarationMessage(view,playerName);
    if(view.phase==="choose_mode"&&allowedToAct(view))return "Выбери: в светлую или в тёмную";
    const turn=view.turn!=null?`Ход: ${playerName(view.turn)}`:"";
    const bidding=auctionMessage(view);
    return view.is_passout?<><strong data-passout-status="true">Распасы</strong>{turn&&<small>{turn}</small>}</>:<><strong>{isPlay?(turn||statusNames[view.status]):(bidding??phaseLabel(view.phase))}</strong>{!isPlay&&turn&&<small>{turn}</small>}{isPlay&&view.turn!==view.my_seat&&view.controller===view.my_seat&&<small>Управляешь открытой рукой</small>}</>;
  })();
  const actions = view && <>
    {view.status === "lobby" && view.lobby_setup && !lobbyReady(view) && <><LobbySetup view={view} profiles={profiles} busy={busy} command={command}/><SeatSwap view={view} profiles={profiles} busy={busy} command={command}/>{view.room_admin&&<button type="button" onClick={copyInvitation}>Скопировать ссылку на комнату</button>}</>}
    {!declareBesideDiscard&&<ActionPanel view={view} busy={busy||!!discardScene.phase} profiles={profiles}
      command={command} regularRoute={regularRoute} setRegularRoute={setRegularRoute}
      onStart={start} onSettle={settle} />}
  </>;
  return <CardBackContext.Provider value={back}><main className={`${styles.root} ${styles.tableRoot}`}>
    <header data-preferans-game-header="true" className={`${styles.header} ${styles.compactHeader}`}>
      <p className={styles.eyebrow}>Частная игра · Преферанс по-запорожски · Версия 1.0</p>
      <div className={styles.headerTools}><div className={styles.headerStatus} data-offline={!online&&!rtReady?"true":undefined}><span className={online ? styles.statusDot : styles.statusOff} aria-hidden="true" />
        {rtReady ? "Обновление в реальном времени" : online ? "Резервная связь" : "Переподключение"}</div></div>
    </header>

    {roomId&&<RoomReturn onReturn={leaveRoom}/>}
    <div className={styles.tableShell}>
        {!roomId && <><Lobby openRoom={openRoom} create={create} busy={busy}/><section className={styles.historyDisclosure}><button type="button" aria-expanded={historyOpen} aria-controls="preferans-lobby-history" onClick={()=>setHistoryOpen(v=>!v)}>{historyOpen?"⌄":"›"} История и рейтинг</button><div id="preferans-lobby-history" hidden={!historyOpen}>{historyOpen&&<PreferansHistory/>}</div></section></>}

        {roomId && !view && <section className={styles.roomBar} aria-label="Комната">
          <div><strong>Комната</strong> <code>{roomId.slice(0, 8)}…{roomId.slice(-6)}</code><span className={styles.subtle}>{invited ? "Приглашение" : "Подключение…"}</span></div>
          <div className={styles.actions}>
            <button type="button" onClick={copyInvitation}>Скопировать приглашение</button>
          </div>
        </section>}

        {roomId && invited && !view && <section className={styles.panel}>
          <h2>Приглашение найдено</h2>
          <p>В комнате {invited.occupied.filter(Boolean).length} из 3 участников. После входа ты займёшь свободное место.</p>
          <button type="button" className={styles.primary} disabled={busy || invited.occupied.every(Boolean)} onClick={join}>Занять место</button>
        </section>}

        {view && <>
          <TableZoom value={tableZoom} onChange={changeTableZoom}/>
          <ImmersiveMenu key={view.room_id} active={view.status !== "lobby"} settings={settings} copy={copyInvitation}
            urgent={Boolean(view.punch_choices?.some(pair=>pair.to===view.my_seat&&pair.replacement===null))}
            shared={view.presentation?.enabled&&view.claim?.status!=="pending" ? openShared : undefined}
            media={LIVE_MEDIA_ENABLED && !archived && view.my_seat !== null
              ? <LiveMediaControls media={liveMedia}/> : <p>Видео и голос пока отключены. Игровая связь от них не зависит.</p>}>
            <GameTable view={view} tableZoom={tableZoom} discardScene={discardScene} onCounter={seat=>command("counter_start",{target:seat})} onSwap={seat=>command("seat_swap_offer",{to:seat})} profiles={profiles} presence={rtReady&&rtPresence?rtPresence:null} localConnected={online||rtReady}
              theme={selectedTheme} roundTable={roundTable} tableSurface={surface} tableOpacity={1-tableTransparency/100} surfaceOpacity={opacity} scoreAdjustment={<ScoreAdjustment view={view} profiles={profiles} busy={busy} adjust={adjust}/>} finalReviewAction={view.final_review?(view.room_admin?<button type="button" disabled={busy} onClick={()=>{if(window.confirm("Подтвердить итоговые расчёты и завершить партию?"))command("final_confirm");}}>Расчёты проверены</button>:<small>Ожидаем подтверждения администратора.</small>):undefined} sheetExit={<SheetExit view={view} busy={busy} command={command}/>} serverNow={serverNow} pendingPlay={localPlay} sortMode={sortMode} busy={busy||!!discardScene.phase||view.claim?.status==="pending"} onReplay={view.presentation?.enabled?()=>openShared("last_trick"):undefined}
              counterPanel={view.controls?.counter&&!view.controls?.undo?<CounterDisplay view={view} name={playerName} serverNow={serverNow} busy={busy} onCancel={()=>command("counter_cancel")}/>:undefined}
              statusLine={<>{tableStatus}<ControlFeedback view={view} name={playerName} serverNow={serverNow}/>{!busy&&pending&&<button type="button" onClick={()=>void mutate(pending.label,pending.run)}>Повторить операцию</button>}</>}
              announcement={view.status==="closed"&&view.sheet_loser!==undefined?<div className={styles.sheetDrama} role="alert"><p>{profiles?.[view.sheet_loser]?.name||seatNames[view.sheet_loser]} ПСИХАНУЛ и выкинул листик.</p><p>По голому удару ему!</p></div>:view.end_reason==="without_three"&&view.declarer!=null&&view.my_seat!==null&&view.my_seat!==view.declarer&&["awaiting_settlement","between"].includes(view.status)?<p className={styles.concedeDrama} role="status">{profiles?.[view.declarer]?.name||seatNames[view.declarer]} зассал и кинул «без трёх»!</p>:undefined}
              claimPanel={<>{view.controls?.undo&&<PreferansControls view={view} profiles={profiles} busy={busy} command={command}/>}{undoAllowed&&undoDraft===undoScope&&<UndoRequest key={undoScope} busy={busy} onCancel={()=>setUndoDraft(null)} onSend={reason=>{setUndoDraft(null);command("undo_request",{reason});}}/>}<ClaimPanel view={view} profiles={profiles} busy={busy} command={command}/><MisereOfferPanel view={view} profiles={profiles} busy={busy} command={command} sortMode={sortMode}/></>}
              claimButton={(undoAllowed||view.can_offer_misere&&view.phase==="play"||view.can_claim&&view.claim?.status!=="pending"||!!view.by_own_options?.length)?<>{undoAllowed&&<button type="button" className={styles.undoIconButton} aria-label="Запросить отмену последнего действия" title="Запросить отмену последнего действия" disabled={busy||!!discardScene.phase||view.claim?.status==="pending"} onClick={()=>setUndoDraft(undoScope)}><UndoIcon/></button>}{view.can_offer_misere&&view.phase==="play"?<button type="button" disabled={busy||!!view.controls?.paused||!!view.controls?.undo} onClick={()=>command("misere_offer")}>{view.my_seat===view.declarer?"Показать карты и предложить что я сыграл":`Согласен, что ${playerName(view.declarer??0)} сыграл мизер`}</button>:null}{view.can_claim&&view.claim?.status!=="pending"?<button type="button" disabled={busy||!!view.controls?.paused||!!view.controls?.undo} title="показать всем мои карты и заявить что все оставшиеся взятки - мои!" onClick={()=>command("claim_offer",{cards:hand})}>Все мои!</button>:null}<ByOwnButton key={`${view.game_id}:${view.played_tricks}:${view.claim?.status}`} view={view} busy={busy||!!discardScene.phase} command={command}/></>:undefined}
              hand={ownHand} handCount={visibleHand.length} handBreaks={visibleHand.filter((card,index)=>index>0&&visibleHand[index-1].suit!==card.suit).length} actions={actions} renderOpenCard={renderOpenCard} onTableDrop={tableDrop} onSeatDrop={seatDrop}
              deck={dealerFor(view)!==null?<Deck enabled={!busy&&view.my_seat===dealerFor(view)&&(mayStart(view)||[0,1,2].some(seat=>mayPassDeck(view,seat)))} canDeal={mayStart(view)} start={start} drag={e=>beginDrag(e,"deck")} end={endDrag}/>:undefined}
              localControls={LIVE_MEDIA_ENABLED&&!archived&&view.my_seat!==null?<div className={styles.ownMediaButtons}>{!liveMedia.state.joined?<button type="button" disabled={!liveMedia.available||liveMedia.state.joining} onClick={liveMedia.join} title="Вход в звонок с выключенными камерой и микрофоном">Связь</button>:<><button type="button" aria-label={liveMedia.state.audio?"Выключить микрофон":"Включить микрофон"} aria-pressed={liveMedia.state.audio} disabled={liveMedia.state.changing} title={liveMedia.state.audio?"Выключить микрофон":"Включить микрофон"} onClick={()=>liveMedia.toggle("audio")}>{liveMedia.state.audio?"🎙":"🔇"}</button><button type="button" aria-label={liveMedia.state.video?"Выключить камеру":"Включить камеру"} aria-pressed={liveMedia.state.video} disabled={liveMedia.state.changing} title={liveMedia.state.video?"Выключить камеру":"Включить камеру"} onClick={()=>liveMedia.toggle("video")}>{liveMedia.state.video?"▣":"⊘"}</button><button type="button" aria-label="Выйти из звонка" onClick={liveMedia.leave}>×</button></>}</div>:undefined}
              mediaForSeat={LIVE_MEDIA_ENABLED && !archived && rtReady && view.my_seat !== null && liveMedia.state.joined ? seat => <MediaSeatTile media={liveMedia} seat={seat} own={seat===view.my_seat}/> : undefined}
              onScore={view.presentation?.enabled?()=>openShared("score_sheet"):undefined}
              objects={view.presentation?.enabled ? <SharedObjects busy={busy||view.claim?.status==="pending"} open={openShared}/> : undefined}
              onField={view.presentation?.overlay&&view.presentation.overlay.kind!=="discard_replay" ? () => shared("overlay_close", {overlay_id: view.presentation?.overlay?.id}) : undefined}
              sharedPanel={view.presentation && <SharedRoom key={view.room_id} view={view} profiles={profiles} busy={busy} command={shared} serverNow={serverNow} scoreAdjustment={<ScoreAdjustment view={view} profiles={profiles} busy={busy} adjust={adjust}/>} sheetExit={<SheetExit view={view} busy={busy} command={command}/>}/>}/>
          </ImmersiveMenu>
        </>}
    </div>
    {!view&&((status) || (!busy&&pending) || (busy&&pending?.label!=="play")) && <div className={styles.notification} role="status" aria-live="polite">
      {busy ? "Операция выполняется…" : status}
      {!busy && pending && <button type="button" onClick={() => void mutate(pending.label, pending.run)}>Повторить операцию</button>}
    </div>}
  </main></CardBackContext.Provider>;
}
