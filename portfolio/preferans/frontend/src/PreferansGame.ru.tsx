"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import {
  ApiError, adjustRoom, createRoom, invitation, joinRoom, newKey, roomView,
  sendCommand, settleRoom, startRoom,
} from "./room-client";
import {
  allowedToAct, cardId, cardLabel, moveCard,
  phaseLabel, ROOM_ID_RE, statusMessage,
  type Card, type CommandAction, type RoomInvitation, type RoomView,
} from "./game-model.ru";
import styles from "./preferans-game.module.css";
import { PreferansControls } from "./PreferansControls.ru";
import { PreferansHistory } from "./PreferansHistory.ru";
import { LiveMediaControls, MediaSeatTile, useLiveMedia } from "./LiveMedia.ru";
import { connectRealtime, type Presence } from "./realtime-client";
import { CardArtwork } from "./CardArtwork.ru";
import { GameTable, PreviousTrick } from "./GameTable.ru";
import { SharedRoom, SharedObjects, type SharedCommand } from "./SharedRoom.ru";
import { replayMoveAllowed, type OverlayKind } from "./presentation-model";
import { ProjectSidebar } from "./ProjectSidebar.ru";
import { Lobby } from "./Lobby.ru";
import { safeProfiles, type Seat, type SeatProfile } from "./table-model";
import { LobbySetup } from "./LobbySetup.ru";
import { SeatSwap } from "./SeatSwap.ru";
import { BidPanel } from "./BidPanel.ru";
import { DealStatus } from "./DealStatus.ru";
import { orderHand, ownCards, mayConcede, type SortMode } from "./interaction-model";

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

function CardFace({ card, selected, playable, onClick, onDragStart, onDragOver, onDrop }: {
  card: Card; selected?: boolean; playable?: boolean; onClick?: () => void;
  onDragStart?: (event: DragEvent<HTMLButtonElement>) => void;
  onDragOver?: (event: DragEvent<HTMLButtonElement>) => void;
  onDrop?: (event: DragEvent<HTMLButtonElement>) => void;
}) {
  const red = card.suit === "D" || card.suit === "H";
  return (
    <button type="button" className={`${styles.playingCard} ${red ? styles.red : ""} ${selected ? styles.selected : ""} ${playable ? styles.playable : ""}`}
      aria-label={`${cardLabel(card)}${selected ? ", выбрана" : ""}`}
      aria-pressed={Boolean(selected)} disabled={!onClick && !onDragStart} onClick={onClick}
      draggable={Boolean(onDragStart)} onDragStart={onDragStart} onDragOver={onDragOver} onDrop={onDrop}
      data-card={cardId(card)}>
      <CardArtwork card={card} decorative />
    </button>
  );
}

function ScoreBoard({ view }: { view: RoomView }) {
  const score = view.score;
  if (!score) return null;
  return (
    <section className={styles.score} aria-labelledby="preferans-score-heading">
      <h3 id="preferans-score-heading">Пуля, гора и висты</h3>
      <div className={styles.scoreTableWrap}>
        <table className={styles.scoreTable}>
          <thead><tr><th scope="col">Игрок</th><th scope="col">Пуля</th><th scope="col">Гора</th><th scope="col">Висты на других</th></tr></thead>
          <tbody>{seatNames.map((label, seat) => <tr key={seat}>
            <th scope="row">{label}</th>
            <td>{score.pool[seat] ?? 0}/{score.target ?? 20}</td>
            <td>{score.hill[seat] ?? 0}</td>
            <td>{score.vists[seat]?.map((n, index) => index === seat ? null : `${seatNames[index]}: ${n}`).filter(Boolean).join(" · ")}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p className={styles.subtle}>Распасы: уровень {score.passout_level}. Расчёт выполняется сервером после раздачи.</p>
    </section>
  );
}

function ActionPanel({ view, busy, selectedCards, selectedCard, command,
  regularRoute, setRegularRoute, passoutRoutes, setPassoutRoute, onStart, onSettle }: {
  view: RoomView; busy: boolean; selectedCards: Card[]; selectedCard: Card | null;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
  regularRoute: "pool" | "hill_first"; setRegularRoute: (x: "pool" | "hill_first") => void;
  passoutRoutes: Array<"pool" | "hill_first" | "help">;
  setPassoutRoute: (seat: number, x: "pool" | "hill_first" | "help") => void;
  onStart: () => void; onSettle: () => void;
}) {
  const myTurn = allowedToAct(view);
  const concede = mayConcede(view) && <div className={styles.concede}><button type="button" disabled={busy} onClick={() => {
    if (window.confirm("Признать игру без трёх? Это начислит штраф в гору без розыгрыша.")) command("without_three");
  }}>Признать «без трёх»</button></div>;
  if (view.status === "playing" && (view.controls?.undo || (view.controls?.paused && !replayMoveAllowed(view)))) {
    return <section className={styles.actionPanel}><h3>Игра приостановлена</h3>
      <p>Закрой общий объект, подтверди готовность или дождись восстановления связи. Ходить сейчас нельзя.</p>
    </section>;
  }
  if (view.status === "between" && view.next_deal && REALTIME_ENABLED) {
    return <section className={styles.actionPanel}><h3>Новая раздача</h3><DealStatus view={view}/></section>;
  }
  if (view.status === "lobby" || view.status === "between") {
    return <section className={styles.actionPanel} aria-labelledby="preferans-actions"><h3 id="preferans-actions">{view.status === "lobby" ? "Сбор игроков" : "Новая раздача"}</h3>
      <p>Занято мест: {view.occupied.filter(Boolean).length} из 3. Новую раздачу запускает администратор комнаты.</p>
      {view.room_admin && <button type="button" className={styles.primary} disabled={busy || Boolean(view.seat_swap) || Boolean(view.controls?.paused) || view.occupied.some(x => !x) || Boolean(view.status === "lobby" && view.lobby_setup && !view.lobby_setup.ready.every(Boolean))} onClick={onStart}>Раздать карты</button>}
    </section>;
  }
  if (view.status === "awaiting_settlement") {
    return <section className={styles.actionPanel} aria-labelledby="preferans-actions"><h3 id="preferans-actions">Сдача завершена</h3>
      <p>Раздача ожидает начисления пули, горы и вистов.</p>
      {view.room_admin ? <>
        {!view.is_passout && <label className={styles.field}>Успешный контракт
          <select value={regularRoute} onChange={(e: ChangeEvent<HTMLSelectElement>) => setRegularRoute(e.target.value as "pool" | "hill_first")}>
            <option value="pool">Записать в пулю</option><option value="hill_first">Сначала погасить гору</option>
          </select></label>}
        {view.is_passout && seatNames.map((label, seat) => <label className={styles.field} key={seat}>{label}: бонус за 0 взяток
          <select value={passoutRoutes[seat]} onChange={(e: ChangeEvent<HTMLSelectElement>) => setPassoutRoute(seat, e.target.value as "pool" | "hill_first" | "help")}>
            <option value="pool">В пулю</option><option value="hill_first">Сначала погасить гору</option><option value="help">Помочь другому</option>
          </select></label>)}
        <button type="button" disabled={busy || Boolean(view.controls?.paused || view.controls?.undo)} className={styles.primary} onClick={onSettle}>Рассчитать раздачу</button>
      </> : <p className={styles.subtle}>Ожидаем расчёт администратора.</p>}
    </section>;
  }
  if (view.status === "archived") return <section className={styles.actionPanel}><h3>Партия архивирована</h3><p>Без игрового поражения, медалей и расчёта незакрытой пули.</p></section>;
  if (view.status === "closed") return <section className={styles.actionPanel}>
    {view.sheet_loser !== undefined ? <><h3>Листик выброшен</h3><p>{seatNames[view.sheet_loser]}: техническое поражение. Соперникам — по первому месту. Незакрытая пуля не дорассчитывается.</p></> : <><h3>Пуля закрыта</h3><p>Все три игрока закрыли пули. Итоговая партия завершена.</p></>}
  </section>;
  if (!myTurn) return concede || null;
  return <section className={styles.actionPanel} aria-labelledby="preferans-actions"><h3 id="preferans-actions">Твоё действие</h3>
    {view.phase === "auction" && <>
      <p>Выбери минимальную ставку. Окончательный контракт объявляется после торгов.</p>
      <BidPanel key={`${view.game_id}:auction`} view={view} busy={busy} command={command}/>
    </>}
    {view.phase === "discard" && <>
      <p>Выбери две карты для скрытого сноса. Выбрано: {selectedCards.length}/2.</p>
      <button type="button" className={styles.primary} disabled={busy || selectedCards.length !== 2}
        onClick={() => command("discard", { cards: selectedCards })}>Снести две карты</button>
    </>}
    {view.phase === "declare" && <>
      <p>После прикупа можно повысить ставку, но нельзя изменить класс контракта.</p>
      <BidPanel key={`${view.game_id}:declare`} view={view} busy={busy} command={command}/>
    </>}
    {(["defense_first", "defense_second", "defense_reconsider"] as string[]).includes(view.phase ?? "") && <>
      <p>{view.phase === "defense_reconsider" ? "Подтверди пас или вернись на вист." : "Защитник выбирает вист или пас."}</p>
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
    {(view.phase === "play" || view.phase === "opening_lead") && <>
      <p>Ходит рука {seatNames[view.turn ?? 0]}. Выбери разрешённую карту и подтверди ход.</p>
      <button type="button" className={styles.primary} disabled={busy || !selectedCard || !(view.legal_cards ?? []).some(c => cardId(c) === cardId(selectedCard))}
        onClick={() => selectedCard && command("play", { card: selectedCard, owner: view.turn })}>
        Сыграть {selectedCard ? cardLabel(selectedCard) : "карту"}
      </button>
    </>}
    {concede}
  </section>;
}

export function PreferansGame({preferenceScope}: {preferenceScope?: string} = {}) {
  const [roomId, setRoomId] = useState("");
  const liveMedia = useLiveMedia();
  const {bind: bindMedia, receive: receiveMedia} = liveMedia;
  const [roomInput, setRoomInput] = useState("");
  const [view, setView] = useState<RoomView | null>(null);
  const [invited, setInvited] = useState<RoomInvitation | null>(null);
  const viewRef = useRef<RoomView | null>(null);
  const serverOffset = useRef(0);
  const serverNow = useCallback(() => Date.now() + serverOffset.current, []);
  const [status, setStatus] = useState("");
  const [online, setOnline] = useState(true);
  const [rtReady, setRtReady] = useState(false);
  const [rtPresence, setRtPresence] = useState<Presence[] | null>(null);
  const [profileState, setProfileState] = useState<{ room: string; seats: string; profiles: SeatProfile[] } | null>(null);
  const [lobbyHistory, setLobbyHistory] = useState(false);
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
  const [passoutRoutes, setPassoutRoutes] = useState<Array<"pool" | "hill_first" | "help">>(["pool", "pool", "pool"]);
  const dragging = useRef<string | null>(null);

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
    setRoomInput(initial);
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
    setStatus(""); setRoomInput(id); setRoomId(id);
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
    setRoomId(""); setRoomInput(""); setView(null); setInvited(null); setSelected([]); setStatus("");
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
      let nextMs = 3_000;
      try {
        const result = await roomView(roomId, viewRef.current?.version);
        if (stopped) return;
        if (!("unchanged" in result)) {
          if (result.presentation) serverOffset.current = result.presentation.server_now_ms - Date.now();
          updateView(result);
          setStatus("");
        }
        setOnline(true);
        errors = 0;
        nextMs = REALTIME_ENABLED ? 20_000 : viewRef.current?.status === "playing" ? 8_000 : 12_000;
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
        nextMs = Math.min(30_000, 8_000 * 2 ** Math.min(errors, 3));
      } finally {
        if (!stopped) {
          timer = setTimeout(tick, document.visibilityState === "hidden" ? Math.max(15_000, nextMs) : nextMs);
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
      onReady: ready => { if (activeRoomRef.current === roomId) { setRtReady(ready); if (!ready) setRtPresence(null); } },
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
    async function heartbeat() {
      if (stopped) return;
      const current = viewRef.current;
      if (!current || current.status === "closed" || current.status === "archived" || (!REALTIME_ENABLED && current.status !== "playing")) return;
      try {
        const response = await sendCommand(current.room_id, newKey(), current.version, "pulse", {});
        if (!stopped && response.version > current.version) setPollKey(value => value + 1);
      } catch (error) {
        // Other players can update the room between our view and heartbeat.
        // The next ordinary poll fetches the new version; never guess it here.
        if (!stopped && error instanceof ApiError && error.status === 409) setPollKey(v => v + 1);
      }
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
    setSelected([]);
  }, [view?.room_id, view?.game_id, view?.phase, view?.turn, view?.controller, view?.played_tricks]);

  useEffect(() => { setOrder([]); }, [view?.room_id, view?.game_id]);

  const mutate = useCallback(async (label: string, run: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true); setStatus("");
    const candidate = { label, run };
    setPending(candidate);
    try {
      const result = await run();
      setPending(null);
      if (result && typeof result === "object" && "room_id" in result && typeof result.room_id === "string") {
        const id = result.room_id;
        if (roomId !== id) openRoom(id);
        else setPollKey(v => v + 1);
      } else setPollKey(v => v + 1);
    } catch (error) {
      const code = error instanceof ApiError ? error.status : 503;
      setStatus(statusMessage(code));
      if ([401, 403, 404, 409, 422].includes(code)) setPending(null);
      if (code === 409) setPollKey(v => v + 1);
    } finally { setBusy(false); }
  }, [busy, openRoom, roomId]);

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
    if (!view) return;
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
    const routes = [...passoutRoutes];
    void mutate("расчёт раздачи", () => settleRoom(view.room_id, token, view.version, regularRoute, routes));
  };
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
  const controlledHand = view?.phase === "opening_lead" || view?.phase === "play"
    ? view.turn === view.my_seat ? view.hand ?? [] : view.open_hands?.find(row => row.seat === view.turn)?.cards ?? []
    : view?.hand ?? [];
  const hand = orderHand(ownCards(view), order, sortMode);
  const selectedCard = controlledHand.find(card => selected.includes(cardId(card))) ?? null;
  const isPlay = view?.phase === "opening_lead" || view?.phase === "play";
  const canInteractCards = Boolean(!busy && view && allowedToAct(view) && (isPlay || view.phase === "discard"));
  const ownPlayable = canInteractCards && (!isPlay || view?.turn === view?.my_seat);
  const onCardSelect = (card: Card) => {
    const id = cardId(card);
    if (!canInteractCards || (isPlay && !legal.has(id))) return;
    setSelected(current => isPlay ? [id] : current.includes(id)
      ? current.filter(x => x !== id) : current.length < 2 ? [...current, id] : current);
  };
  const renderOpenCard = (card: Card, seat: Seat) => {
    const playable = Boolean(isPlay && canInteractCards && view?.turn === seat && legal.has(cardId(card)));
    return <CardFace card={card} selected={selected.includes(cardId(card)) && playable} playable={playable}
      onClick={playable ? () => onCardSelect(card) : undefined}/>;
  };
  const reorder = (from: string, to: string) => setOrder(moveCard(hand.map(cardId), from, to));
  const copyInvitation = () => {
    if (!roomId) return;
    void navigator.clipboard.writeText(window.location.href).then(() => setStatus("Ссылка скопирована."))
      .catch(() => setStatus("Не удалось скопировать. Скопируй адрес из браузера."));
  };

  const shared: SharedCommand = (action, args = {}) => {
    if (view?.presentation) command(action, { ...args, presentation_version: view.presentation.revision });
  };
  const openShared = (kind: OverlayKind) => shared("overlay_open", {kind});
  const ownHand = view && <div className={styles.handsPanel}>
    <div className={styles.handTitle}><h3>Твоя рука</h3>
      <label>Сортировка <select aria-label="Сортировка карт" value={sortMode} onChange={e => changeSort(e.target.value === "suit" ? "suit" : "grouped")}>
        <option value="grouped">По длине масти</option><option value="suit">По порядку мастей</option>
      </select></label>
      <button type="button" onClick={() => setOrder([])}>Автосортировка</button>
      {isPlay && view.turn !== view.my_seat && view.controller === view.my_seat && <span>Ты управляешь открытой рукой соперника. Выбери карту на его месте.</span>}
    </div>
    <div className={styles.handRow} aria-label="Игровые карты">
      {hand.map((card, index) => <div data-hand-card="true" className={styles.cardWithSort} key={cardId(card)}>
        <CardFace card={card} selected={ownPlayable && selected.includes(cardId(card))} playable={ownPlayable && (view.phase === "discard" || legal.has(cardId(card)))}
          onClick={ownPlayable && (view.phase === "discard" || legal.has(cardId(card))) ? () => onCardSelect(card) : undefined}
          onDragStart={e => { dragging.current = cardId(card); e.dataTransfer.effectAllowed = "move"; }}
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); if (dragging.current) reorder(dragging.current, cardId(card)); dragging.current = null; }} />
        <div className={styles.sortControls}>
          <button type="button" aria-label={`Переместить ${cardLabel(card)} влево`} disabled={index === 0} onClick={() => reorder(cardId(card), cardId(hand[index - 1]))}>‹</button>
          <button type="button" aria-label={`Переместить ${cardLabel(card)} вправо`} disabled={index === hand.length - 1} onClick={() => reorder(cardId(card), cardId(hand[index + 1]))}>›</button>
        </div>
      </div>)}
      {!hand.length && <span className={styles.subtle}>Нет карт для отображения</span>}
    </div>
  </div>;
  const actions = view && <>
    <ReleaseControls key={`${view.room_id}:${view.game_id}`} view={view} busy={busy} command={command}/>
    {view.status === "lobby" && view.lobby_setup && <RulesetEditor view={view} busy={busy} command={command}/>}
    {view.status === "lobby" && view.lobby_setup && <><LobbySetup view={view} busy={busy} command={command} /><SeatSwap view={view} profiles={profiles} busy={busy} command={command}/></>}
    <ActionPanel view={view} busy={busy} selectedCards={chosenCards}
      selectedCard={selectedCard} command={command} regularRoute={regularRoute} setRegularRoute={setRegularRoute}
      passoutRoutes={passoutRoutes} setPassoutRoute={(seat, val) => setPassoutRoutes(old => old.map((v, i) => i === seat ? val : v))}
      onStart={start} onSettle={settle} />
  </>;
  const rules = <section className={styles.panel}><h3>Правила партии</h3>
    <p>Ставка в торговле — минимальная. После прикупа заказчик объявляет окончательный контракт.</p>
    <p>В свой ход доступны только действия и карты, разрешённые сервером. Ходы подтверждаются отдельно.</p>
    <p>Для отмены последнего хода нужны два согласия. Счётчик ставит соперник; задержка и штраф подтверждаются сервером.</p>
    <p>{rtReady ? "Обновление в реальном времени." : REALTIME_ENABLED ? "Резервное обновление примерно каждые 20 секунд." : "Обновление примерно каждые 8 секунд во время игры."} Не передавай ссылку посторонним.</p>
  </section>;
  return <main className={`${styles.root} ${styles.tableRoot}`}>
    <header className={styles.header}>
      <div><p className={styles.eyebrow}>Частная игра · Преферанс по-запорожски</p><h1>Преферанс</h1>
        <p className={styles.headerSub}>Три игрока. Твои карты видишь только ты. Все решения проверяет сервер.</p></div>
      <div className={styles.headerStatus}><span className={online ? styles.statusDot : styles.statusOff} aria-hidden="true" />
        {rtReady ? "Обновление в реальном времени" : online ? (REALTIME_ENABLED ? "Резервная связь" : "Связь активна") : "Переподключение"}</div>
    </header>

    {(liveMedia.state.joined || liveMedia.state.joining) && <div className={styles.actions}>
      <button type="button" onClick={liveMedia.leave}>Отключить камеру, микрофон и звонок</button>
    </div>}
    <div className={styles.tableShell}>
        {!roomId && <><Lobby roomInput={roomInput} setRoomInput={setRoomInput} openRoom={openRoom} create={create} busy={busy}/>
          <button type="button" aria-expanded={lobbyHistory} onClick={() => setLobbyHistory(v => !v)}>История и рейтинг</button>
          {lobbyHistory && <PreferansHistory/>}</>}

        {roomId && <section className={styles.roomBar} aria-label="Комната">
          <div><strong>Комната</strong> <code>{roomId.slice(0, 8)}…{roomId.slice(-6)}</code><span className={styles.subtle}>{view ? statusNames[view.status] : invited ? "Приглашение" : "Подключение…"}</span></div>
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
          <div className={styles.gameHead}>
            <div><span className={styles.eyebrow}>{statusNames[view.status]}</span><h2>{phaseLabel(view.phase)}</h2>
              <p>{view.my_seat !== null ? `Твоё место: ${profiles?.[view.my_seat]?.name || seatNames[view.my_seat]}` : "Ты наблюдаешь без доступа к чужим картам."}</p></div>
            <div className={styles.gameBadges}><span>Версия {view.version}</span></div>
          </div>
          <ProjectSidebar key={view.room_id} active={view.status !== "lobby"} rules={rules}
            score={<ScoreBoard view={view}/>} history={<PreferansHistory refreshKey={view.status === "closed" ? view.version : 0}/>}
            controls={<PreferansControls view={view} busy={busy} command={command} adjust={adjust}/>}
            last={<PreviousTrick view={view}/>}
            urgent={Boolean(view.reveal || view.controls?.counter || view.controls?.undo || view.sheet_offers?.some(offer => offer.to === view.my_seat))}
            shared={view.presentation?.enabled ? openShared : undefined}
            media={LIVE_MEDIA_ENABLED && !archived && view.my_seat !== null
              ? <LiveMediaControls media={liveMedia}/> : <p>Видео и голос пока отключены. Игровая связь от них не зависит.</p>}>
            <GameTable view={view} profiles={profiles} presence={rtReady ? rtPresence : null}
              hand={ownHand} actions={actions} renderOpenCard={renderOpenCard}
              mediaForSeat={LIVE_MEDIA_ENABLED && !archived && rtReady && view.my_seat !== null && liveMedia.state.joined ? seat => <MediaSeatTile media={liveMedia} seat={seat} own={seat===view.my_seat}/> : undefined}
              objects={view.presentation?.enabled ? <SharedObjects view={view} busy={busy} open={openShared}/> : undefined}
              onWidow={view.presentation?.enabled ? () => openShared("widow_replay") : undefined}
              onField={view.presentation?.overlay ? () => shared("overlay_close", {overlay_id: view.presentation?.overlay?.id}) : undefined}
              sharedPanel={view.presentation && <SharedRoom key={view.room_id} view={view} profiles={profiles} busy={busy} command={shared} serverNow={serverNow} scoreTable={<ScoreBoard view={view}/>}/>}/>
          </ProjectSidebar>
        </>}
    </div>
    {(status || pending || busy) && <div className={styles.notification} role="status" aria-live="polite">
      {busy ? "Операция выполняется…" : status}
      {!busy && pending && <button type="button" onClick={() => void mutate(pending.label, pending.run)}>Повторить операцию</button>}
    </div>}
  </main>;
}
