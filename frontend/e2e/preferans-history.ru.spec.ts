import { expect, test } from "@playwright/test";
import { sortedRankings, timeline, isHistoryPayload, isRankingPayload, type Ranking, type Result } from
  "../../portfolio/preferans/frontend/src/history-model";

const rank = (id: string, gold: number, games = 2): Ranking => ({
  id, gold, games, silver: 0, third: 0, technical_losses: 0, net_vists: gold * 10,
  vists_given: 0, vists_received: 0, timer_hill: 0,
  bare_given: 0, bare_received: 0, ordinary_given: 0, ordinary_received: 0,
  total_duration_ms: 60_000, timed_games: 1, last_finished_at_ms: 1000,
});
const game = (room_id: string, finished_at_ms: number, ids: string[]): Result => ({
  room_id, finished_at_ms, started_at_ms: 100, duration_ms: 100, active_ms: null,
  reason: "pool_closed", deal_count: 1, ruleset_hash: "f", ruleset_version: 1,
  punches: [], punches_confirmed: false, ledger_entry_count: 2, ledger_sha256: "f",
  players: ids.map((id, seat) => ({ id, seat, net_vists: 0, place: seat + 1,
    gold: Number(seat === 0), silver: Number(seat === 1), third: Number(seat === 2),
    technical_losses: 0, pool: 20, hill: 0, vists_given: 0, vists_received: 0,
    timer_hill: 0, bare_given: 0, bare_received: 0, ordinary_given: 0,
    ordinary_received: 0,
  })),
});

test("ranking sorts descending gold by default, and both directions for all columns", () => {
  const rows = [rank("z", 1), rank("a", 3), rank("b", 1)];
  expect(sortedRankings(rows, "gold", true).map(r => r.id)).toEqual(["a", "b", "z"]);
  expect(sortedRankings(rows, "gold", false).map(r => r.id)).toEqual(["b", "z", "a"]);
  expect(sortedRankings(rows, "id", false).map(r => r.id)).toEqual(["a", "b", "z"]);
  expect(rows.map(r => r.id)).toEqual(["z", "a", "b"]);
});

test("graph respects historical completion order despite API sorting", () => {
  const recent = game("new", 2000, ["a", "b", "c"]);
  const old = game("old", 1000, ["b", "c", "a"]);
  const curves = timeline([recent, old], ["a", "b", "c"], "gold");
  expect(curves[0].map(p => p.total)).toEqual([0, 1]);
  expect(curves[1].map(p => p.total)).toEqual([1, 1]);
  expect(curves[0].map(p => p.room_id)).toEqual(["old", "new"]);
});

test("public contract validates result and ranking envelope", () => {
  const result = game("a".repeat(32), 1000, ["a".repeat(24), "b".repeat(24), "c".repeat(24)]);
  expect(isHistoryPayload({ results: [result], has_more: false })).toBe(true);
  expect(isHistoryPayload({ results: [{ room_id: "game", players: [] }], has_more: false })).toBe(false);
  expect(isRankingPayload({ rankings: [rank("a".repeat(24), 1)] })).toBe(true);
  expect(isRankingPayload({ rankings: [{ id: "a", games: "1", gold: "1" }] })).toBe(false);
});
