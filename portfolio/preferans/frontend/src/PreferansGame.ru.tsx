"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import {
  ApiError, createRoom, invitation, joinRoom, newKey, roomView,
  sendCommand, settleRoom, startRoom,
} from "./room-client";
import {
  allowedToAct, bidLabel, cardId, cardLabel, moveCard,
  phaseLabel, ROOM_ID_RE, sortedHand, statusMessage, suitSymbol,
  type Card, type CommandAction, type RoomInvitation, type RoomView,
} from "./game-model.ru";
import styles from "./preferans-game.module.css";

type Mutation = { label: string; run: () => Promise<unknown> };
const seatNames = ["Игрок 1", "Игрок 2", "Игрок 3"];
const statusNames: Record<RoomView["status"], string> = {
  lobby: "Ожидание игроков", playing: "Идёт игра",
  awaiting_settlement: "Подсчёт результатов", between: "Между раздачами", closed: "Партия завершена",
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
      aria-pressed={Boolean(selected)} disabled={!onClick} onClick={onClick}
      draggable={Boolean(onDragStart)} onDragStart={onDragStart} onDragOver={onDragOver} onDrop={onDrop}
      data-card={cardId(card)}>
      <span className={styles.cardCorner}>{cardLabel(card)}</span>
      <span className={styles.cardSymbol} aria-hidden="true">{suitSymbol(card.suit)}</span>
      <span className={styles.cardFoot} aria-hidden="true">{cardLabel(card)}</span>
    </button>
  );
}

function SeatSummary({ seat, view }: { seat: number; view: RoomView }) {
  const isMe = view.my_seat === seat;
  const active = view.turn === seat;
  const cards = view.open_hands?.find(row => row.seat === seat)?.cards;
  return (
    <section className={`${styles.player} ${active ? styles.playerTurn : ""}`} aria-label={`${seatNames[seat]}${isMe ? ", ты" : ""}`}>
      <div className={styles.playerTitle}>
        <strong>{seatNames[seat]} {isMe && <span className={styles.me}>(ты)</span>}</strong>
        {active && <span className={styles.turnLabel}>Ход</span>}
      </div>
      <span className={styles.subtle}>{view.occupied[seat] ? "За столом" : "Место свободно"}</span>
      <div className={styles.playerStats}>
        <span>Карт: {view.hand_counts?.[seat] ?? "—"}</span>
        <span>Взяток: {view.tricks_won?.[seat] ?? "—"}</span>
      </div>
      {cards && cards.length > 0 && (
        <div className={styles.exposedCards} aria-label={`Открытые карты: ${seatNames[seat]}`}>
          {cards.map(card => <span className={styles.exposedCard} key={cardId(card)}>{cardLabel(card)}</span>)}
        </div>
      )}
    </section>
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

function TrickArea({ view }: { view: RoomView }) {
  return (
    <div className={styles.trickGrid}>
      <div className={styles.trickBox}>
        <h3>Текущая взятка</h3>
        <div className={styles.trickCards}>
          {(view.trick ?? []).length ? view.trick?.map((play, index) => <div key={`${index}-${cardId(play.card)}`} className={styles.trickCard}>
            <span>{seatNames[play.owner]}</span><strong>{cardLabel(play.card)}</strong>
          </div>) : <span className={styles.subtle}>Карты ещё не сыграны</span>}
        </div>
      </div>
      <div className={styles.trickBox}>
        <h3>Последняя взятка</h3>
        <div className={styles.trickCards}>
          {(view.last_trick ?? []).length ? view.last_trick?.map((play, index) => <div key={`${index}-${cardId(play.card)}`} className={styles.trickCard}>
            <span>{seatNames[play.owner]}</span><strong>{cardLabel(play.card)}</strong>
          </div>) : <span className={styles.subtle}>Пока нет</span>}
        </div>
      </div>
    </div>
  );
}

function ActionPanel({ view, busy, selectedCards, selectedBid, setSelectedBid, selectedCard, command,
  regularRoute, setRegularRoute, passoutRoutes, setPassoutRoute, onStart, onSettle }: {
  view: RoomView; busy: boolean; selectedCards: Card[]; selectedBid: string;
  setSelectedBid: (value: string) => void; selectedCard: Card | null;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
  regularRoute: "pool" | "hill_first"; setRegularRoute: (x: "pool" | "hill_first") => void;
  passoutRoutes: Array<"pool" | "hill_first" | "help">;
  setPassoutRoute: (seat: number, x: "pool" | "hill_first" | "help") => void;
  onStart: () => void; onSettle: () => void;
}) {
  const myTurn = allowedToAct(view);
  const bids = view.phase === "auction" ? view.legal_bids ?? [] : view.legal_contracts ?? [];
  const chosenBid = bids.find(b => JSON.stringify(b) === selectedBid) ?? bids[0];
  const chooseBid = (action: "bid" | "declare") => {
    if (chosenBid) command(action, { bid: chosenBid });
  };
  if (view.status === "lobby" || view.status === "between") {
    return <section className={styles.actionPanel} aria-labelledby="preferans-actions"><h3 id="preferans-actions">{view.status === "lobby" ? "Сбор игроков" : "Новая раздача"}</h3>
      <p>Занято мест: {view.occupied.filter(Boolean).length} из 3. Новую раздачу запускает администратор комнаты.</p>
      {view.room_admin && <button type="button" className={styles.primary} disabled={busy || view.occupied.some(x => !x)} onClick={onStart}>Раздать карты</button>}
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
        <button type="button" disabled={busy} className={styles.primary} onClick={onSettle}>Рассчитать раздачу</button>
      </> : <p className={styles.subtle}>Ожидаем расчёт администратора.</p>}
    </section>;
  }
  if (view.status === "closed") return <section className={styles.actionPanel}><h3>Пуля закрыта</h3><p>Все три игрока закрыли пули. Итоговая партия завершена.</p></section>;
  if (!myTurn) return <section className={styles.actionPanel} aria-live="polite"><h3 id="preferans-actions">Ожидание хода</h3>
    <p>{view.controller !== null && view.controller !== undefined && (view.phase === "play" || view.phase === "opening_lead")
      ? `${seatNames[view.controller]} управляет ходом ${seatNames[view.turn ?? 0]}.`
      : view.turn !== null && view.turn !== undefined ? `Сейчас очередь: ${seatNames[view.turn]}.` : "Ожидаем другого игрока."}</p>
  </section>;
  return <section className={styles.actionPanel} aria-labelledby="preferans-actions"><h3 id="preferans-actions">Твоё действие</h3>
    {view.phase === "auction" && <>
      <p>Выбери минимальную ставку. Окончательный контракт объявляется после торгов.</p>
      {bids.length > 0 && <label className={styles.field}>Ставка
        <select value={chosenBid ? JSON.stringify(chosenBid) : ""} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedBid(e.target.value)}>
          {bids.map((bid, index) => <option key={`${index}-${bidLabel(bid)}`} value={JSON.stringify(bid)}>{bidLabel(bid)}</option>)}
        </select></label>}
      <div className={styles.actions}>
        <button type="button" className={styles.primary} disabled={!chosenBid || busy} onClick={() => chooseBid("bid")}>Заявить ставку</button>
        {view.can_say_here && <button type="button" disabled={busy} onClick={() => command("here")}>Здесь</button>}
        <button type="button" disabled={busy} onClick={() => command("pass")}>Пас</button>
      </div>
    </>}
    {view.phase === "discard" && <>
      <p>Выбери две карты для скрытого сноса. Выбрано: {selectedCards.length}/2.</p>
      <button type="button" className={styles.primary} disabled={busy || selectedCards.length !== 2}
        onClick={() => command("discard", { cards: selectedCards })}>Снести две карты</button>
    </>}
    {view.phase === "declare" && <>
      <p>После прикупа можно повысить ставку, но нельзя изменить класс контракта.</p>
      {bids.length > 0 && <label className={styles.field}>Окончательный контракт
        <select value={chosenBid ? JSON.stringify(chosenBid) : ""} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedBid(e.target.value)}>
          {bids.map((bid, index) => <option key={`${index}-${bidLabel(bid)}`} value={JSON.stringify(bid)}>{bidLabel(bid)}</option>)}
        </select></label>}
      <button type="button" className={styles.primary} disabled={busy || !chosenBid} onClick={() => chooseBid("declare")}>Заказать игру</button>
    </>}
    {(["defense_first", "defense_second", "defense_reconsider"] as string[]).includes(view.phase ?? "") && <>
      <p>Защитник выбирает вист или пас.</p>
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
    {view.declarer === view.my_seat && view.contract?.kind !== "misere" && view.contract?.kind !== "misere_no_widow" &&
      (view.played_tricks ?? 0) === 0 && (view.trick ?? []).length === 0 &&
      ["defense_first", "defense_second", "defense_reconsider", "choose_mode", "opening_lead", "play"].includes(view.phase ?? "") &&
      <div className={styles.concede}><button type="button" disabled={busy} onClick={() => {
        if (window.confirm("Признать игру без трёх? Это начислит штраф в гору без розыгрыша.")) command("without_three");
      }}>Признать «без трёх»</button></div>}
  </section>;
}

export function PreferansGame() {
  const [roomId, setRoomId] = useState("");
  const [roomInput, setRoomInput] = useState("");
  const [view, setView] = useState<RoomView | null>(null);
  const [invited, setInvited] = useState<RoomInvitation | null>(null);
  const viewRef = useRef<RoomView | null>(null);
  const [status, setStatus] = useState("");
  const [online, setOnline] = useState(true);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Mutation | null>(null);
  const [pollKey, setPollKey] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [order, setOrder] = useState<string[]>([]);
  const [selectedBid, setSelectedBid] = useState("");
  const [regularRoute, setRegularRoute] = useState<"pool" | "hill_first">("pool");
  const [passoutRoutes, setPassoutRoutes] = useState<Array<"pool" | "hill_first" | "help">>(["pool", "pool", "pool"]);
  const dragging = useRef<string | null>(null);

  const updateView = useCallback((next: RoomView) => {
    viewRef.current = next;
    setView(next);
    setInvited(null);
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get("room");
    const initial = fromUrl && ROOM_ID_RE.test(fromUrl) ? fromUrl : "";
    setRoomInput(initial);
    setRoomId(initial);
  }, []);

  const openRoom = useCallback((id: string) => {
    if (!ROOM_ID_RE.test(id)) { setStatus("Нужен идентификатор комнаты из 32 символов (0–9, a–f)."); return; }
    viewRef.current = null;
    setView(null); setInvited(null); setSelected([]); setOrder([]); setSelectedBid("");
    setStatus(""); setRoomInput(id); setRoomId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("room", id);
    window.history.replaceState({}, "", url);
    setPollKey(v => v + 1);
  }, []);

  const leaveRoom = useCallback(() => {
    viewRef.current = null;
    setRoomId(""); setRoomInput(""); setView(null); setInvited(null); setSelected([]); setStatus("");
    const url = new URL(window.location.href);
    url.searchParams.delete("room");
    window.history.replaceState({}, "", url);
  }, []);

  // One polling loop per room. The server never returns an unchanged view to a different user.
  useEffect(() => {
    if (!roomId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let errors = 0;
    async function tick() {
      let nextMs = 3_000;
      try {
        const result = await roomView(roomId, viewRef.current?.version);
        if (stopped) return;
        if (!("unchanged" in result)) {
          updateView(result);
          setStatus("");
        }
        setOnline(true);
        errors = 0;
        nextMs = viewRef.current?.status === "playing" ? 3_000 : 6_000;
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
            // No further reads of revoked content; keep the public error visible.
            return;
          }
        }
        nextMs = Math.min(30_000, 3_000 * 2 ** Math.min(errors, 4));
      } finally {
        if (!stopped) {
          timer = setTimeout(tick, document.visibilityState === "hidden" ? Math.max(15_000, nextMs) : nextMs);
        }
      }
    }
    void tick();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
  }, [roomId, pollKey, updateView]);

  useEffect(() => {
    setSelected([]); setSelectedBid("");
  }, [view?.game_id, view?.phase]);

  useEffect(() => {
    const current = view?.hand ?? [];
    setOrder(old => {
      const known = old.filter(id => current.some(card => cardId(card) === id));
      const additions = sortedHand(current, []).map(cardId).filter(id => !known.includes(id));
      return [...known, ...additions];
    });
  }, [view?.hand]);

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
  const chosenCards = useMemo(() => {
    const all = [...(view?.hand ?? []), ...(view?.phase === "discard" && view.declarer === view.my_seat ? view.widow ?? [] : [])];
    return all.filter(card => selected.includes(cardId(card)));
  }, [view, selected]);
  const legal = useMemo(() => new Set((view?.legal_cards ?? []).map(cardId)), [view?.legal_cards]);
  const controlledHand = view?.phase === "opening_lead" || view?.phase === "play"
    ? view.turn === view.my_seat ? view.hand ?? [] : view.open_hands?.find(row => row.seat === view.turn)?.cards ?? []
    : view?.hand ?? [];
  const hand = sortedHand(controlledHand, order);
  const selectedCard = hand.find(card => selected.includes(cardId(card))) ?? null;
  const isPlay = view?.phase === "opening_lead" || view?.phase === "play";
  const canInteractCards = Boolean(view && allowedToAct(view) && (isPlay || view.phase === "discard"));
  const onCardSelect = (card: Card) => {
    const id = cardId(card);
    if (!canInteractCards || (isPlay && !legal.has(id))) return;
    setSelected(current => isPlay ? [id] : current.includes(id)
      ? current.filter(x => x !== id) : current.length < 2 ? [...current, id] : current);
  };
  const reorder = (from: string, to: string) => setOrder(current => moveCard(current, from, to));
  const copyInvitation = () => {
    if (!roomId) return;
    void navigator.clipboard.writeText(window.location.href).then(() => setStatus("Ссылка скопирована."))
      .catch(() => setStatus("Не удалось скопировать. Скопируй адрес из браузера."));
  };

  return <main className={styles.root}>
    <header className={styles.header}>
      <div><p className={styles.eyebrow}>Частная игра · Преферанс по-запорожски</p><h1>Преферанс</h1>
        <p className={styles.headerSub}>Три игрока. Твои карты видишь только ты. Все решения проверяет сервер.</p></div>
      <div className={styles.headerStatus}><span className={online ? styles.statusDot : styles.statusOff} aria-hidden="true" />
        {online ? "Связь активна" : "Переподключение"}</div>
    </header>

    <div className={styles.shell}>
      <div className={styles.primaryColumn}>
        {!roomId && <section className={styles.panel} aria-labelledby="preferans-join-heading">
          <h2 id="preferans-join-heading">Создать игру или присоединиться</h2>
          <p>Нужны три разных аккаунта Portfolio Lab с доступом Test или Admin к проекту Preferans.</p>
          <button type="button" className={styles.primary} onClick={create} disabled={busy}>Создать комнату</button>
          <div className={styles.joinField}><label htmlFor="room-id">Код приглашения</label>
            <input id="room-id" spellCheck={false} autoComplete="off" value={roomInput} onChange={(e: ChangeEvent<HTMLInputElement>) => setRoomInput(e.target.value.trim().toLowerCase())} placeholder="32 символа" />
            <button type="button" onClick={() => openRoom(roomInput)} disabled={busy || !ROOM_ID_RE.test(roomInput)}>Найти комнату</button>
          </div>
        </section>}

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
              <p>{view.my_seat !== null ? `Твоё место: ${seatNames[view.my_seat]}` : "Ты наблюдаешь без доступа к чужим картам."}</p>
            </div>
            <div className={styles.gameBadges}><span>Версия {view.version}</span>{view.contract && <span>Контракт: {bidLabel(view.contract)}</span>}
              {view.is_passout && <span>Распасы</span>}
            </div>
          </div>
          <section className={styles.table} aria-label="Игровой стол">
            <div className={styles.rivals}>
              {[0, 1, 2].filter(s => s !== view.my_seat).map(s => <SeatSummary view={view} seat={s} key={s} />)}
            </div>
            <TrickArea view={view} />
            {view.my_seat !== null && <SeatSummary view={view} seat={view.my_seat} />}
          </section>
          <div className={styles.handsPanel}>
            <div className={styles.handTitle}><h3>{isPlay && view.turn !== view.my_seat ? `Открытая рука: ${seatNames[view.turn ?? 0]}` : "Твоя рука"}</h3>
              <span>Коснись карты для выбора; перетаскивай или используй кнопки для сортировки</span></div>
            <div className={styles.handRow} aria-label="Игровые карты">
              {hand.map((card, index) => <div className={styles.cardWithSort} key={cardId(card)}>
                <CardFace card={card} selected={selected.includes(cardId(card))} playable={canInteractCards && (view.phase === "discard" || legal.has(cardId(card)))}
                  onClick={() => onCardSelect(card)}
                  onDragStart={e => { dragging.current = cardId(card); e.dataTransfer.effectAllowed = "move"; }}
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => { e.preventDefault(); if (dragging.current) reorder(dragging.current, cardId(card)); dragging.current = null; }} />
                <div className={styles.sortControls}>
                  <button type="button" aria-label={`Переместить ${cardLabel(card)} влево`} disabled={index === 0} onClick={() => reorder(cardId(card), cardId(hand[index - 1]))}>‹</button>
                  <button type="button" aria-label={`Переместить ${cardLabel(card)} вправо`} disabled={index === hand.length - 1} onClick={() => reorder(cardId(card), cardId(hand[index + 1]))}>›</button>
                </div>
              </div>)}
              {view.phase === "discard" && view.declarer === view.my_seat && (view.widow ?? []).map(card => <div className={styles.cardWithSort} key={`widow-${cardId(card)}`}>
                <CardFace card={card} selected={selected.includes(cardId(card))} playable onClick={() => onCardSelect(card)} />
                <span className={styles.widowLabel}>Прикуп</span>
              </div>)}
              {!hand.length && <span className={styles.subtle}>Нет карт для отображения</span>}
            </div>
          </div>
          <ActionPanel view={view} busy={busy} selectedCards={chosenCards} selectedBid={selectedBid} setSelectedBid={setSelectedBid}
            selectedCard={selectedCard} command={command} regularRoute={regularRoute} setRegularRoute={setRegularRoute}
            passoutRoutes={passoutRoutes} setPassoutRoute={(seat, val) => setPassoutRoutes(old => old.map((v, i) => i === seat ? val : v))}
            onStart={start} onSettle={settle} />
          <ScoreBoard view={view} />
        </>}
      </div>
      <aside className={styles.sideColumn}>
        <section className={styles.panel}>
          <h2>Правила партии</h2>
          <p>Ставка в торговле — минимальная. После прикупа заказчик объявляет окончательный контракт.</p>
          <p>В свой ход доступны только действия и карты, разрешённые сервером. Ходы подтверждаются отдельно.</p>
          <p className={styles.subtle}>Отмена хода голосованием и таймеры появятся на этапе PR 6.</p>
        </section>
        <section className={styles.panel}>
          <h2>Подключение</h2>
          <p>Состояние обновляется примерно каждые 3 секунды во время игры. После разрыва связи текущая партия восстанавливается по коду комнаты.</p>
          <p className={styles.subtle}>Не передавай ссылку посторонним. Сам по себе код не предоставляет доступ без аккаунта и гранта.</p>
          {view?.phase === "auction" && view.high_bid && <p>Лидирует: <strong>{bidLabel(view.high_bid)}</strong></p>}
          {view?.widow && view.widow.length > 0 && <p>Открытый прикуп: <strong>{view.widow.map(cardLabel).join(" ")}</strong></p>}
        </section>
      </aside>
    </div>
    {(status || pending || busy) && <div className={styles.notification} role="status" aria-live="polite">
      {busy ? "Операция выполняется…" : status}
      {!busy && pending && <button type="button" onClick={() => void mutate(pending.label, pending.run)}>Повторить операцию</button>}
    </div>}
  </main>;
}
