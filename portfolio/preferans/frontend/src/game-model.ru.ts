/** Public, allow-listed types only. No Firestore game state or Firebase credentials. */
import { isPresentation, replayMoveAllowed, type Presentation } from "./presentation-model";
import { isSeat, isSheetOffers, type SheetOffer } from "./sheet-exit-model";
import { isSeatSwap, type SeatSwap } from "./seat-swap-model";
import { isReleaseProjection, type Reveal, type RevealedCard, type PunchChoice } from "./release-model";
export type Suit = "S" | "C" | "D" | "H";
export type Card = { suit: Suit; rank: number };
export type Bid = {
  kind: "regular" | "misere" | "misere_no_widow" | "ten_no_widow";
  level: number | null;
  suit: Suit | null;
};
export type Phase =
  | "auction" | "discard" | "declare" | "defense_first" | "defense_second"
  | "defense_reconsider" | "choose_mode" | "opening_lead" | "play" | "finished";
export type Score = {
  pool: number[]; hill: number[]; vists: number[][]; target?: number;
  passout_level: number; closed: boolean; ruleset_hash: string;
};
export type Adjustment = {
  field: "pool" | "hill" | "vist"; seat: number; against: number | null;
  delta: number; before: number; after: number; reason: string;
  actor_seat: number | null; created_at_ms: number; game_version: number;
};
export type RoomControls = {
  paused: boolean;
  pause_reasons?: string[];
  counter: null | { target: number; initiator: number; deadline_ms: number | null;
    remaining_ms?: number; penalty: number; periods: number; period_ms: number };
  undo: null | { kind: "card_play" | "auction_bid"; requester: number;
    deadline_ms: number | null; remaining_ms?: number; reason: string; votes: Record<string, boolean>; can_vote: boolean };
  can_request_undo: boolean;
  adjustments: Adjustment[];
  policy?: { counter_seconds: number; counter_multiplier: number; undo_seconds: number };
};
export type RoomView = {
  room_id: string; version: number;
  status: "lobby" | "playing" | "awaiting_settlement" | "between" | "closed" | "archived";
  occupied: boolean[]; my_seat: number | null; room_admin: boolean; game_id: string | null;
  controls?: RoomControls;
  presentation?: Presentation;
  sheet_loser?: number; sheet_offers?: SheetOffer[];
  seat_swap?: SeatSwap; seat_revision?: number;
  can_archive?: boolean; archived_at_ms?: number;
  reveal?: Reveal; revealed_cards?: RevealedCard[]; punch_choices?: PunchChoice[];
  last_trick_suit?: Suit | null;
  lobby_setup?: { ready: boolean[]; dealer: number; target: number; ruleset: string; ruleset_version: number; ruleset_name?: string; ruleset_parameters?: Record<string,number|number[]>; ruleset_snapshot_hash?: string };
  phase?: Phase; turn?: number | null; controller?: number | null;
  dealer?: number; first_hand?: number; is_passout?: boolean; played_tricks?: number;
  declarer?: number | null; contract?: Bid | null; high_bid?: Bid | null;
  auction_calls?: Array<{kind: "bid" | "pass" | "here"; bid: Bid | null} | null>;
  last_trick_winner?: number | null;
  next_deal?: { after_game_id: string; deadline_ms: number | null; remaining_ms: number | null };
  hand?: Card[]; hand_counts?: number[]; legal_cards?: Card[];
  legal_bids?: Bid[]; legal_contracts?: Bid[]; can_say_here?: boolean;
  trick?: Array<{ owner: number; card: Card }>;
  last_trick?: Array<{ owner: number; card: Card }>;
  open_hands?: Array<{ seat: number; cards: Card[] }>;
  widow?: Card[]; defense?: Array<string | null>; mode?: string | null;
  tricks_won?: number[]; score?: Score; end_reason?: string | null;
};
export type RoomInvitation = {
  room_id: string; version: number; status: "lobby"; occupied: boolean[];
};
export type ApiFailure = { status: number; detail: string };
export type CommandAction =
  | "bid" | "pass" | "here" | "discard" | "declare" | "defense" | "mode"
  | "play" | "without_three" | "pulse" | "counter_start" | "undo_request" | "undo_vote" | "preset" | "lobby_ready" | "lobby_config" | "overlay_open" | "overlay_close" | "break_start" | "break_ready" | "music" | "sheet_offer" | "sheet_reply" | "sheet_discard" | "seat_swap_offer" | "seat_swap_vote" | "reveal_report" | "reveal_propose" | "reveal_vote" | "punch_choose" | "archive" | "ruleset_select";

export const ROOM_ID_RE = /^[0-9a-f]{32}$/;
const SUITS: Record<Suit, { symbol: string; label: string }> = {
  S: { symbol: "♠", label: "Пики" }, C: { symbol: "♣", label: "Трефы" },
  D: { symbol: "♦", label: "Бубны" }, H: { symbol: "♥", label: "Червы" },
};
export const suitSymbol = (suit: Suit) => SUITS[suit]?.symbol ?? "?";
export const suitLabel = (suit: Suit) => SUITS[suit]?.label ?? "?";
export const cardId = (card: Card) => `${card.rank}${card.suit}`;
export const cardLabel = (card: Card) => `${rankLabel(card.rank)}${suitSymbol(card.suit)}`;
export function rankLabel(rank: number) {
  const ranks: Record<number, string> = { 11: "В", 12: "Д", 13: "К", 14: "Т" };
  return ranks[rank] ?? String(rank);
}
export function bidLabel(bid: Bid): string {
  if (bid.kind === "misere") return "Мизер";
  if (bid.kind === "misere_no_widow") return "Мизер без прикупа";
  return `${bid.level}${bid.suit ? suitSymbol(bid.suit) : "БК"}${bid.kind === "ten_no_widow" ? " без прикупа" : ""}`;
}
export function sortedHand(hand: Card[], order: string[]): Card[] {
  const ranks = new Map(order.map((id, i) => [id, i]));
  return [...hand].sort((a, b) => {
    const x = ranks.get(cardId(a));
    const y = ranks.get(cardId(b));
    if (x !== undefined && y !== undefined) return x - y;
    if (x !== undefined) return -1;
    if (y !== undefined) return 1;
    const suit = "SCDH".indexOf(a.suit) - "SCDH".indexOf(b.suit);
    return suit || b.rank - a.rank;
  });
}
export function moveCard(order: string[], from: string, to: string): string[] {
  if (!order.includes(from) || !order.includes(to) || from === to) return order;
  const result = order.filter(id => id !== from);
  result.splice(result.indexOf(to), 0, from);
  return result;
}
export function allowedToAct(view: RoomView): boolean {
  if (view.my_seat === null || view.status !== "playing" ||
      (view.controls?.paused && !replayMoveAllowed(view)) || view.controls?.undo) return false;
  if (view.phase === "opening_lead" || view.phase === "play") {
    return view.controller === view.my_seat;
  }
  if (view.phase === "discard" || view.phase === "declare") {
    return view.declarer === view.my_seat;
  }
  return view.turn === view.my_seat;
}
export function phaseLabel(phase?: Phase): string {
  const labels: Record<Phase, string> = {
    auction: "Торговля", discard: "Снос прикупа", declare: "Заказ игры",
    defense_first: "Решение защиты", defense_second: "Решение защиты",
    defense_reconsider: "Повторное решение", choose_mode: "Светлая или тёмная",
    opening_lead: "Первый ход", play: "Розыгрыш", finished: "Раздача завершена",
  };
  return phase ? labels[phase] : "Ожидание игроков";
}

/** Never trust a server response merely because it parses as JSON. */
export function isRoomView(value: unknown): value is RoomView {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  if (!isReleaseProjection(v)) return false;
  if (v.seat_revision !== undefined && (!Number.isSafeInteger(v.seat_revision) || Number(v.seat_revision) < 0 || !isSeat(v.my_seat))) return false;
  if (v.seat_swap !== undefined && (v.status !== "lobby" || !isSeat(v.my_seat) || !isSeatSwap(v.seat_swap))) return false;
  if (v.sheet_loser !== undefined && (!isSeat(v.sheet_loser) || v.status !== "closed" || v.hand !== undefined || v.legal_cards !== undefined)) return false;
  if (v.sheet_offers !== undefined && (!isSheetOffers(v.sheet_offers) || !isSeat(v.my_seat) || !["playing", "between", "awaiting_settlement"].includes(String(v.status)))) return false;
  if (v.presentation !== undefined && (!isPresentation(v.presentation) || v.my_seat === null)) return false;
  if (v.next_deal !== undefined) {
    const clock = v.next_deal as Record<string, unknown> | null;
    if (!clock || typeof clock !== "object" || v.status !== "between" ||
      typeof clock.after_game_id !== "string" || clock.after_game_id !== v.game_id ||
      !(clock.deadline_ms === null || (Number.isSafeInteger(clock.deadline_ms) && Number(clock.deadline_ms) >= 0)) ||
      !(clock.remaining_ms === null || (Number.isInteger(clock.remaining_ms) && Number(clock.remaining_ms) >= 0 && Number(clock.remaining_ms) <= 5000)) ||
      ((clock.deadline_ms === null) === (clock.remaining_ms === null))) return false;
  }
  if (v.lobby_setup !== undefined) {
    const setup = v.lobby_setup as Record<string, unknown> | null;
    if (!setup || typeof setup !== "object" || !Array.isArray(setup.ready) || setup.ready.length !== 3 || !setup.ready.every(x => typeof x === "boolean") || ![0,1,2].includes(Number(setup.dealer)) || typeof setup.dealer !== "number" || !Number.isInteger(setup.target) || Number(setup.target)<1 || Number(setup.target)>1000 || typeof setup.ruleset !== "string" || !Number.isInteger(setup.ruleset_version)) return false;
  }
  return typeof v.room_id === "string" && ROOM_ID_RE.test(v.room_id) &&
    Number.isSafeInteger(v.version) && (v.version as number) >= 0 &&
    ["lobby", "playing", "awaiting_settlement", "between", "closed", "archived"].includes(String(v.status)) &&
    Array.isArray(v.occupied) && v.occupied.length === 3 && v.occupied.every(x => typeof x === "boolean") &&
    (v.my_seat === null || [0, 1, 2].includes(v.my_seat as number)) &&
    typeof v.room_admin === "boolean";
}
export function isInvitation(value: unknown): value is RoomInvitation {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  return typeof v.room_id === "string" && ROOM_ID_RE.test(v.room_id) &&
    Number.isSafeInteger(v.version) && v.status === "lobby" &&
    Array.isArray(v.occupied) && v.occupied.length === 3 && v.occupied.every(x => typeof x === "boolean");
}
export function statusMessage(status: number): string {
  switch (status) {
    case 401: return "Сессия истекла. Войди в Portfolio Lab заново.";
    case 403: return "Нет доступа. Проверь грант Preferans (Test или Admin).";
    case 404: return "Комната не найдена или тебе не разрешён вход.";
    case 409: return "Комната изменилась. Обновляем состояние.";
    case 422: return "Этот ход не разрешён. Обнови состояние партии.";
    case 502: case 503: return "Сервер недоступен. Проверь соединение и повтори действие.";
    default: return "Не удалось выполнить запрос. Попробуй ещё раз.";
  }
}
