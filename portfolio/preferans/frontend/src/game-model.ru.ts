/** Public, allow-listed types only. No Firestore game state or Firebase credentials. */
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
export type RoomView = {
  room_id: string; version: number;
  status: "lobby" | "playing" | "awaiting_settlement" | "between" | "closed";
  occupied: boolean[]; my_seat: number | null; room_admin: boolean; game_id: string | null;
  phase?: Phase; turn?: number | null; controller?: number | null;
  dealer?: number; first_hand?: number; is_passout?: boolean; played_tricks?: number;
  declarer?: number | null; contract?: Bid | null; high_bid?: Bid | null;
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
  | "play" | "without_three";

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
  if (view.my_seat === null || view.status !== "playing") return false;
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
  return typeof v.room_id === "string" && ROOM_ID_RE.test(v.room_id) &&
    Number.isSafeInteger(v.version) && (v.version as number) >= 0 &&
    ["lobby", "playing", "awaiting_settlement", "between", "closed"].includes(String(v.status)) &&
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
