"use client";

import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import { type CommandAction, type RoomView } from "./game-model.ru";
import styles from "./preferans-game.module.css";

const names = ["Игрок 1", "Игрок 2", "Игрок 3"];
type AdjustRequest = { field: "pool" | "hill" | "vist"; seat: number; against: number | null;
  delta: number; reason: string };

function secondsLeft(deadline: number | null, remaining: number | undefined, now: number): number {
  return Math.max(0, Math.ceil(((deadline === null ? remaining ?? 0 : deadline - now) / 1000)));
}

export function PreferansControls({ view, busy, command, adjust }: {
  view: RoomView;
  busy: boolean;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
  adjust: (value: AdjustRequest) => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  const [counterSec, setCounterSec] = useState(180);
  const [multiplier, setMultiplier] = useState(3);
  const [voteSec, setVoteSec] = useState(120);
  const [field, setField] = useState<AdjustRequest["field"]>("hill");
  const [seat, setSeat] = useState(0);
  const [against, setAgainst] = useState(1);
  const [deltaText, setDeltaText] = useState("1");
  const [reason, setReason] = useState("");
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);
  const controls = view.controls;
  if (!controls || view.status === "archived") return null;
  if (view.status === "lobby") {
    return view.room_admin ? <section className={styles.controlPanel} aria-labelledby="preferans-policy-heading">
      <h3 id="preferans-policy-heading">Параметры до начала партии</h3>
      <p className={styles.subtle}>Текущий набор: счётчик {controls.policy?.counter_seconds ?? 180} сек.,
        множитель {controls.policy?.counter_multiplier ?? 3}, отмена {controls.policy?.undo_seconds ?? 120} сек.
        Изменения допускаются только до первой раздачи.</p>
      <div className={styles.adjustGrid}>
        <label>Счётчик, секунд <input type="number" min={60} max={600} step={30} value={counterSec}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setCounterSec(Number(e.target.value))} /></label>
        <label>Множитель штрафа <input type="number" min={1} max={6} step={1} value={multiplier}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setMultiplier(Number(e.target.value))} /></label>
        <label>Голосование, секунд <input type="number" min={30} max={300} step={30} value={voteSec}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setVoteSec(Number(e.target.value))} /></label>
      </div>
      <button type="button" disabled={busy || !Number.isInteger(counterSec) || !Number.isInteger(multiplier) ||
        !Number.isInteger(voteSec) || counterSec < 60 || counterSec > 600 || multiplier < 1 || multiplier > 6 ||
        voteSec < 30 || voteSec > 300} onClick={() => command("preset", {
          counter_seconds: counterSec, counter_multiplier: multiplier, undo_seconds: voteSec,
        })}>Сохранить параметры</button>
    </section> : null;
  }
  const active = view.status === "playing";
  const target = view.phase === "play" || view.phase === "opening_lead" ? view.controller : view.turn;
  const canCounter = active && view.my_seat !== null && target !== null &&
    target !== undefined && target !== view.my_seat && !controls.paused &&
    !controls.undo && !controls.counter;
  const counter = controls.counter;
  const vote = controls.undo;
  const delta = Number(deltaText);
  const before = field === "hill" ? view.score?.hill[seat] :
    field === "pool" ? view.score?.pool[seat] : view.score?.vists[seat]?.[against];
  const after = before === undefined ? null : before + delta;
  const validAdjustment = Number.isSafeInteger(delta) && delta !== 0 && Math.abs(delta) <= 1000 &&
    reason.trim().length >= 5 && reason.trim().length <= 180 && after !== null && after >= 0 &&
    (field !== "pool" || after <= (view.score?.target ?? 20)) &&
    (field !== "vist" || seat !== against);
  return <section className={styles.controlPanel} aria-labelledby="preferans-controls-heading">
    <h3 id="preferans-controls-heading">Управление игрой</h3>
    {controls.paused && <p role="status" className={styles.controlAlert}>Пауза: таймеры заморожены. Проверь общие панели, перерыв и соединение.</p>}
    {counter && <div className={styles.controlNote} aria-live="off">
      <strong>На счётчике: {names[counter.target]}</strong>
      <span>Поставил: {names[counter.initiator]}</span>
      <span>До следующего штрафа: {secondsLeft(counter.deadline_ms, counter.remaining_ms, now)} сек.</span>
      <span>Штраф: {counter.penalty} в гору · истечений: {counter.periods}</span>
    </div>}
    {canCounter && <button type="button" disabled={busy} onClick={() => command("counter_start")}>Поставить на счётчик ({controls.policy?.counter_seconds ?? 180} сек.)</button>}
    {active && controls.can_request_undo && !controls.paused && !vote &&
      <button type="button" disabled={busy} onClick={() => {
        const answer = window.prompt("Почему отменить последний ход или ставку?", "Ошибся при выборе");
        if (answer && answer.trim().length >= 5) command("undo_request", { reason: answer.trim() });
      }}>Запросить отмену последнего действия</button>}
    {vote && <div className={styles.controlNote} role="group" aria-label="Голосование за отмену">
      <strong>Запрос на отмену: {vote.kind === "card_play" ? "карты" : "ставки"}</strong>
      <p>{names[vote.requester]}: {vote.reason}</p>
      <p>Осталось: {secondsLeft(vote.deadline_ms, vote.remaining_ms, now)} сек. · Голосов: {Object.keys(vote.votes).length}/2</p>
      {vote.can_vote && !controls.paused && <div className={styles.actions}>
        <button type="button" disabled={busy} onClick={() => command("undo_vote", { approve: true })}>Простить</button>
        <button type="button" disabled={busy} onClick={() => command("undo_vote", { approve: false })}>Отказать</button>
      </div>}
    </div>}
    {view.room_admin && view.status !== "closed" && view.score && <details name="preferans-control-group" className={styles.adjustments}>
      <summary>Корректировка расчётов (только администратор)</summary>
      <p className={styles.subtle}>Только активная партия. Каждое изменение остаётся в журнале. Исправление ошибки — новая обратная операция.</p>
      <div className={styles.adjustGrid}>
        <label>Запись <select value={field} onChange={(e: ChangeEvent<HTMLSelectElement>) => setField(e.target.value as AdjustRequest["field"])}>
          <option value="hill">Гора</option><option value="pool">Пуля</option><option value="vist">Висты</option>
        </select></label>
        <label>Игрок <select value={seat} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSeat(Number(e.target.value))}>
          {names.map((name, i) => <option key={i} value={i}>{name}</option>)}
        </select></label>
        {field === "vist" && <label>На кого <select value={against} onChange={(e: ChangeEvent<HTMLSelectElement>) => setAgainst(Number(e.target.value))}>
          {names.map((name, i) => <option key={i} value={i}>{name}</option>)}
        </select></label>}
        <label>Изменение (+ или −) <input type="number" step="1" min="-1000" max="1000" value={deltaText} onChange={(e: ChangeEvent<HTMLInputElement>) => setDeltaText(e.target.value)} /></label>
        <label>Причина <input maxLength={180} value={reason} onChange={(e: ChangeEvent<HTMLInputElement>) => setReason(e.target.value)} placeholder="Почему изменён расчёт" /></label>
      </div>
      <p aria-live="polite">Предпросмотр: {before ?? "?"} → {after ?? "?"}</p>
      <button type="button" disabled={busy || !validAdjustment} onClick={() => {
        if (!validAdjustment || !window.confirm(`Записать корректировку: ${before} → ${after}?`)) return;
        adjust({ field, seat, against: field === "vist" ? against : null, delta, reason: reason.trim() });
      }}>Подтвердить корректировку</button>
    </details>}
    {(controls.adjustments?.length ?? 0) > 0 && <details name="preferans-control-group" className={styles.adjustments}>
      <summary>Журнал корректировок ({controls.adjustments.length} последних)</summary>
      <ol>{controls.adjustments.map((entry, index) => <li key={`${entry.game_version}-${index}`}>
        {entry.field} · {names[entry.seat]}{entry.against !== null ? ` → ${names[entry.against]}` : ""}:
        {" "}{entry.before} → {entry.after}. {entry.reason}
      </li>)}</ol>
    </details>}
  </section>;
}
