"use client";

import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import { type CommandAction, type RoomView } from "./game-model.ru";
import styles from "./preferans-game.module.css";

import type { SeatProfile } from "./table-model";
function secondsLeft(deadline: number | null, remaining: number | undefined, now: number): number {
  return Math.max(0, Math.ceil(((deadline === null ? remaining ?? 0 : deadline - now) / 1000)));
}

export function PreferansControls({ view, profiles, busy, command }: {
  profiles:SeatProfile[]|null;
  view: RoomView;
  busy: boolean;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  const [counterSec, setCounterSec] = useState(180);
  const [multiplier, setMultiplier] = useState(3);
  const [voteSec, setVoteSec] = useState(120);
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);
  const names=[0,1,2].map(i=>profiles?.[i]?.name||`Игрок ${i+1}`);
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
  const canCounter = active && view.claim?.status!=="pending" && view.my_seat !== null && target !== null &&
    target !== undefined && target !== view.my_seat && !controls.paused &&
    !controls.undo && !controls.counter;
  const counter = controls.counter;
  const vote = controls.undo;
  return <section className={styles.controlPanel} aria-labelledby="preferans-controls-heading">
    <h3 id="preferans-controls-heading">Счётчик и отмена действий</h3>
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
  </section>;
}
