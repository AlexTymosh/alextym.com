/** Public, allow-listed historical summaries only. Never game state or account UIDs. */
export type Player = {
  id: string; seat: number; net_vists: number; place: number | null;
  gold: number; silver: number; third: number; technical_losses: number;
  pool: number; hill: number; vists_given: number; vists_received: number;
  timer_hill: number; bare_given: number; bare_received: number;
  ordinary_given: number; ordinary_received: number;
};
export type Result = {
  room_id: string; finished_at_ms: number; started_at_ms: number | null;
  duration_ms: number | null; active_ms: number | null; reason: string;
  deal_count: number; ruleset_hash: string; ruleset_version: number; ruleset_id?: string; punch_choices?: Array<{from:number;to:number;bare:number;ordinary:number;replacement:number|null}>;
  players: Player[]; punches: Array<{ from: number; to: number; bare: number; ordinary: number }>;
  punches_confirmed: boolean; ledger_entry_count: number; ledger_sha256: string;
};
export type Ranking = {
  id: string; games: number; gold: number; silver: number; third: number;
  technical_losses: number; net_vists: number; vists_given: number;
  vists_received: number; timer_hill: number;
  bare_given: number; bare_received: number;
  ordinary_given: number; ordinary_received: number;
  total_duration_ms: number; timed_games: number; last_finished_at_ms: number;
};
export type SortField = keyof Ranking | "win_rate" | "average_vists" | "average_duration";
export type Metric = "gold" | "games" | "net_vists" | "bare_received" | "bare_given" | "vists_given";
export function numeric(row: Ranking, key: SortField): number {
  if (key === "win_rate") return row.games ? 100 * row.gold / row.games : 0;
  if (key === "average_vists") return row.games ? row.net_vists / row.games : 0;
  if (key === "average_duration") return row.timed_games ? row.total_duration_ms / row.timed_games / 60000 : 0;
  if (key === "id") return 0;
  return row[key];
}
export function sortedRankings(rows: Ranking[], key: SortField, desc: boolean, names:Record<string,string>={}): Ranking[] {
  return [...rows].sort((a, b) => {
    const compare = key === "id" ? (names[a.id]??a.id).localeCompare(names[b.id]??b.id) : numeric(a, key) - numeric(b, key);
    return (desc ? -compare : compare) || a.id.localeCompare(b.id);
  });
}
export function timeline(results: Result[], ids: string[], metric: Metric) {
  const chronological = [...results].sort((a, b) => a.finished_at_ms - b.finished_at_ms || a.room_id.localeCompare(b.room_id));
  return ids.map(id => {
    let sum = 0;
    return chronological.map((game, index) => {
      const player = game.players.find(p => p.id === id);
      sum += metric === "games" ? Number(Boolean(player)) : player?.[metric] ?? 0;
      return { index, total: sum, room_id: game.room_id, finished_at_ms: game.finished_at_ms };
    });
  });
}
const safeCount = (value: unknown): value is number => Number.isSafeInteger(value) && typeof value === "number";
const safeNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const isPlayer = (value: unknown): value is Player => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const p = value as Record<string, unknown>;
  return typeof p.id === "string" && /^[a-f0-9]{24}$/.test(p.id) &&
    [0, 1, 2].includes(p.seat as number) &&
    (p.place === null || [1, 2, 3].includes(p.place as number)) &&
    ["net_vists", "gold", "silver", "third", "technical_losses", "pool", "hill",
      "vists_given", "vists_received", "timer_hill", "bare_given", "bare_received",
      "ordinary_given", "ordinary_received"].every(k => safeNumber(p[k]));
};
export function isHistoryPayload(value: unknown): value is { results: Result[]; has_more: boolean } {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  return Array.isArray(v.results) && typeof v.has_more === "boolean" && v.results.every(item => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return false;
    const r = item as Record<string, unknown>;
    return typeof r.room_id === "string" && /^[a-f0-9]{32}$/.test(r.room_id) &&
      safeCount(r.finished_at_ms) && (r.started_at_ms === null || safeCount(r.started_at_ms)) &&
      (r.duration_ms === null || safeCount(r.duration_ms)) &&
      Array.isArray(r.players) && r.players.length === 3 && r.players.every(isPlayer) &&
      safeCount(r.deal_count) && safeCount(r.ruleset_version) &&
      typeof r.ruleset_hash === "string" && typeof r.ledger_sha256 === "string" &&
      safeCount(r.ledger_entry_count) && typeof r.reason === "string";
  });
}
export function isRankingPayload(value: unknown): value is { rankings: Ranking[]; player_names?:Record<string,string> } {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  if (v.player_names !== undefined && (!v.player_names || typeof v.player_names!=="object" || Array.isArray(v.player_names) || !Object.entries(v.player_names).every(([id,name])=>/^[a-f0-9]{24}$/.test(id)&&typeof name==="string"&&name.length<=161&&!/[@\u0000-\u001f\u007f-\u009f]/.test(name)))) return false;
  return Array.isArray(v.rankings) && v.rankings.every(item => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return false;
    const r = item as Record<string, unknown>;
    return typeof r.id === "string" && /^[a-f0-9]{24}$/.test(r.id) &&
      ["games", "gold", "silver", "third", "technical_losses", "net_vists",
        "vists_given", "vists_received", "timer_hill", "bare_given", "bare_received",
        "ordinary_given", "ordinary_received", "total_duration_ms", "timed_games",
        "last_finished_at_ms"].every(k => safeCount(r[k]));
  });
}
