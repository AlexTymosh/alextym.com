"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import styles from "./preferans-history.module.css";

import {
  type Result, type Ranking, type SortField, type Metric,
  numeric, sortedRankings, timeline, isHistoryPayload, isRankingPayload,
} from "./history-model";

const graphMetrics: Metric[] = ["gold", "games", "net_vists", "bare_received", "bare_given", "vists_given"];
const columns: Array<{ key: SortField; title: string }> = [
  { key: "id", title: "Игрок" }, { key: "games", title: "Партий" },
  { key: "gold", title: "Золото" }, { key: "silver", title: "Серебро" },
  { key: "third", title: "Третьих мест" }, { key: "technical_losses", title: "Тех. поражений" },
  { key: "win_rate", title: "Побед, %" },
  { key: "net_vists", title: "Висты, итог" },
  { key: "average_vists", title: "Висты / партию" },
  { key: "timer_hill", title: "Штрафы счётчика" },
  { key: "ordinary_received", title: "Обыч. получено" },
  { key: "ordinary_given", title: "Обыч. нанесено" },
  { key: "bare_received", title: "Голые получено" },
  { key: "bare_given", title: "Голые нанесено" },
  { key: "average_duration", title: "Ср. время, мин" },
  { key: "last_finished_at_ms", title: "Последняя партия" },
];
const graphLabels: Record<Metric, string> = {
  gold: "Золотые медали", games: "Партии", net_vists: "Итоговые висты",
  bare_received: "Голые удары получены", bare_given: "Голые удары нанесены",
  vists_given: "Написанные висты",
};
const strokes = ["#d9a441", "#41a8b3", "#c7779e"];

const playerLabel = (id: string) => `Игрок ${id.slice(0, 6)}`;
const when = (ms: number) => new Date(ms).toLocaleString("ru-RU", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
function formatted(row: Ranking, key: SortField) {
  if (key === "id") return playerLabel(row.id);
  if (key === "last_finished_at_ms") return when(row.last_finished_at_ms);
  if (key === "average_duration" && !row.timed_games) return "—";
  if (["win_rate", "average_vists", "average_duration"].includes(key)) return numeric(row, key).toFixed(1);
  return String(numeric(row, key));
}
async function fetchJson(path: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(`/api/preferans/${path}`, {
    credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" }, signal,
  });
  if (!response.ok) throw new Error(response.status === 403 ? "Недостаточно прав для просмотра истории." :
    response.status === 401 ? "Войди в Portfolio Lab заново." :
    `История временно недоступна (HTTP ${response.status}).`);
  return response.json();
}

function LineGraph({ results, ids, metric }: { results: Result[]; ids: string[]; metric: Metric }) {
  const chronological = [...results].sort((a,b) => a.finished_at_ms - b.finished_at_ms || a.room_id.localeCompare(b.room_id));
  const series = timeline(results, ids, metric).map(points => points.map(p => ({
    x: 42 + p.index * 680 / Math.max(1, chronological.length - 1),
    y: p.total, game: chronological[p.index],
  })));
  const all = series.flat().map(point => point.y);
  const low = Math.min(0, ...all);
  const high = Math.max(low + 1, ...all);
  const scale = (value: number) => 202 - (value - low) * 160 / (high - low);
  return <div className={styles.chartScroll}>
    <svg viewBox="0 0 760 260" className={styles.chart} role="img" aria-label={`${graphLabels[metric]}. Три линии игроков по завершённым партиям.`}>
      {[0, 1, 2, 3, 4].map(n => {
        const value = low + n * (high - low) / 4;
        const y = scale(value);
        return <g key={n}><line x1="42" x2="722" y1={y} y2={y} stroke="currentColor" strokeOpacity=".13" />
          <text x="37" y={y + 4} fontSize="11" textAnchor="end" fill="currentColor">{Number.isInteger(value) ? value : value.toFixed(1)}</text></g>;
      })}
      {series.map((points, index) => <g key={ids[index]}>
        {points.length > 0 && <polyline fill="none" stroke={strokes[index]} strokeWidth="3" strokeLinejoin="round"
          points={points.map(p => `${p.x},${scale(p.y)}`).join(" ")} />}
        {points.map((point, n) => <circle key={`${point.game.room_id}-${n}`} cx={point.x} cy={scale(point.y)} r="3.8"
          fill={strokes[index]}><title>{playerLabel(ids[index])}: {point.y} · {when(point.game.finished_at_ms)}</title></circle>)}
      </g>)}
      <text x="42" y="246" fontSize="11" fill="currentColor">Старые партии</text>
      <text x="722" y="246" textAnchor="end" fontSize="11" fill="currentColor">Новые партии</text>
    </svg>
  </div>;
}

export function PreferansHistory({ refreshKey = 0 }: { refreshKey?: number }) {
  const [results, setResults] = useState<Result[]>([]);
  const [rankings, setRankings] = useState<Ranking[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sortKey, setSortKey] = useState<SortField>("gold");
  const [descending, setDescending] = useState(true);
  const [metric, setMetric] = useState<Metric>("gold");
  const [selected, setSelected] = useState<string[]>([]);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetchJson("history?limit=100", controller.signal), fetchJson("rankings", controller.signal)])
      .then(([history, rank]) => {
        if (!isHistoryPayload(history) || !isRankingPayload(rank)) throw new Error("Некорректный ответ сервера статистики.");
        setResults(history.results); setHasMore(history.has_more); setRankings(rank.rankings); setError("");
        setSelected(current => current.length ? current : history.results[0]?.players.map(p => p.id) ?? []);
      }).catch(exc => { if (!controller.signal.aborted) setError(exc instanceof Error ? exc.message : "История недоступна."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refreshKey, reload]);
  const sorted = useMemo(() => sortedRankings(rankings, sortKey, descending), [rankings, sortKey, descending]);
  const changeSort = useCallback((key: SortField) => {
    if (key === sortKey) setDescending(previous => !previous);
    else { setSortKey(key); setDescending(key !== "id"); }
    if (graphMetrics.includes(key as Metric)) setMetric(key as Metric);
  }, [sortKey]);
  const choose = (index: number, value: string) => setSelected(previous => previous.map((id, i) => i === index ? value : id));
  return <section className={styles.root} aria-labelledby="preferans-history-heading">
    <header className={styles.heading}><div><h2 id="preferans-history-heading">История и рейтинг</h2>
      <p>Только зафиксированные завершённые партии · статистика пересчитывается из неизменяемых итогов</p></div>
      <button type="button" onClick={() => { setLoading(true); setReload(n => n + 1); }}>Обновить</button>
    </header>
    {loading && <p role="status">Загружаем результаты…</p>}
    {error && <p role="alert" className={styles.alert}>{error}</p>}
    {!loading && !error && <>
      <p className={styles.note}>Игровые имена пока представлены устойчивыми псевдонимами. Висты — итоговая нулесуммовая разница.
        Удары рассчитаны по базовому правилу; замена голого удара на обычные ещё не подтверждается игроком.</p>
      <div className={styles.tableScroll}><table className={styles.table}>
        <caption>Общий рейтинг · {rankings.length} игроков · сортировка по любой колонке</caption>
        <thead><tr>{columns.map(column => <th scope="col" key={column.key} aria-sort={sortKey === column.key ? descending ? "descending" : "ascending" : "none"}>
          <button type="button" onClick={() => changeSort(column.key)}>
            {column.title}{sortKey === column.key ? descending ? " ↓" : " ↑" : ""}
          </button></th>)}</tr></thead>
        <tbody>{sorted.map(row => <tr key={row.id}>{columns.map(column =>
          <td key={column.key}>{formatted(row, column.key)}</td>)}</tr>)}</tbody>
      </table></div>
      {!rankings.length && <p className={styles.note}>Завершённых партий ещё нет.</p>}
      {results.length > 0 && <>
        <div className={styles.chartHead}><h3>Динамика трёх участников</h3>
          <label>Показатель <select value={metric} onChange={(e: ChangeEvent<HTMLSelectElement>) => setMetric(e.target.value as Metric)}>
            {graphMetrics.map(key => <option key={key} value={key}>{graphLabels[key]}</option>)}</select></label></div>
        <div className={styles.legend}>{[0, 1, 2].map(index => <label key={index}>
          <span className={styles.swatch} style={{ background: strokes[index] }} /> Игрок {index + 1}
          <select value={selected[index] ?? ""} onChange={(e: ChangeEvent<HTMLSelectElement>) => choose(index, e.target.value)}>
            {rankings.map(row => <option key={row.id} value={row.id}>{playerLabel(row.id)}</option>)}
          </select></label>)}</div>
        {selected.length === 3 && new Set(selected).size === 3 ?
          <LineGraph results={results} ids={selected} metric={metric} /> :
          <p className={styles.note}>Для графика выбери трёх разных игроков.</p>}
        {hasMore && <p className={styles.note}>График и список показывают только последние 100 партий. Рейтинг учитывает все завершённые партии.</p>}
      </>}
      <h3>Последние партии</h3>
      <div className={styles.historyList}>{results.map(game => <details key={game.room_id} className={styles.result}>
        <summary>{when(game.finished_at_ms)} · {game.deal_count} раздач · {game.reason === "sheet_discarded" ? "Техническое поражение" : "Пуля закрыта"}</summary>
        <div className={styles.resultBody}><p>Правила v{game.ruleset_version} · {game.ruleset_hash.slice(0, 12)} ·
          {game.duration_ms === null ? " продолжительность неизвестна" : ` ${(game.duration_ms / 60000).toFixed(1)} мин`}</p>
          <table><thead><tr><th>Игрок</th><th>Висты</th><th>Место</th><th>Пуля</th><th>Гора</th></tr></thead>
          <tbody>{game.players.map(player => <tr key={player.id}>
            <td>{playerLabel(player.id)}</td><td>{player.net_vists}</td><td>{player.place ?? "Ничья"}</td>
            <td>{player.pool}</td><td>{player.hill}</td></tr>)}</tbody></table>
          <p className={styles.note}>Проводок: {game.ledger_entry_count} · контрольная сумма {game.ledger_sha256.slice(0, 12)}.</p>
        </div>
      </details>)}</div>
    </>}
  </section>;
}
