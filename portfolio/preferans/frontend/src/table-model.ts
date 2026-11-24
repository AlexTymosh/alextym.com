import type { Card, RoomView } from "./game-model.ru";

export type SeatPosition = "left" | "right" | "bottom";
export type Seat = 0 | 1 | 2;
export type SeatProfile = { name: string | null; avatar: string | null };
export type RoomSummary = {
  room_id: string; status: RoomView["status"]; occupied: boolean[]; mine: boolean;
};
export const validSeat = (seat: unknown): seat is Seat => seat === 0 || seat === 1 || seat === 2;

// Clockwise server order: from the bottom seat, the next player is on the left.
// Observer uses seat 0 as a fixed reference, but is never treated as a player.
export function tableSeats(me: number | null): Record<SeatPosition, Seat> {
  const origin = validSeat(me) ? me : 0;
  return { left: ((origin + 1) % 3) as Seat, right: ((origin + 2) % 3) as Seat, bottom: origin };
}
export function seatPosition(me: number | null, seat: number): SeatPosition | null {
  if (!validSeat(seat)) return null;
  const positions = tableSeats(me);
  return positions.left === seat ? "left" : positions.right === seat ? "right" : "bottom";
}
export function actorSeat(view: RoomView): Seat | null {
  if (view.status !== "playing" || view.controls?.paused || view.controls?.undo) return null;
  const actor = view.phase === "play" || view.phase === "opening_lead" ? view.controller
    : view.phase === "discard" || view.phase === "declare" ? view.declarer : view.turn;
  return validSeat(actor) ? actor : null;
}
export function isCard(value: unknown): value is Card {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return ["S", "C", "D", "H"].includes(String(v.suit)) && Number.isInteger(v.rank) &&
    Number(v.rank) >= 7 && Number(v.rank) <= 14;
}
export function opponentCards(view: RoomView, seat: Seat): { open: Card[] | null; count: number } {
  // Do not look at view.hand or infer cards from the full deck.
  if (seat === view.my_seat || !view.occupied[seat]) return { open: null, count: 0 };
  const exposed = view.open_hands?.find(h => h.seat === seat)?.cards;
  if (Array.isArray(exposed) && exposed.length <= 12 && exposed.every(isCard)) {
    return { open: exposed, count: exposed.length };
  }
  const n = view.hand_counts?.[seat];
  return { open: null, count: typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= 12 ? n : 0 };
}
export function safeProfiles(value: unknown): SeatProfile[] | null {
  if (!value || typeof value !== "object") return null;
  const profiles = (value as Record<string, unknown>).profiles;
  if (!Array.isArray(profiles) || profiles.length !== 3) return null;
  return profiles.map(p => {
    if (!p || typeof p !== "object") return { name: null, avatar: null };
    const name = typeof p.name === "string" && p.name.length <= 160 && !/[@\u0000-\u001f\u007f-\u009f]/.test(p.name) ? p.name : null;
    const avatar = typeof p.avatar === "string" && p.avatar.length <= 133_400 && /^data:image\/webp;base64,[A-Za-z0-9+/=]+$/.test(p.avatar) ? p.avatar : null;
    return { name, avatar };
  });
}
export function safeDirectory(value: unknown): { rooms: RoomSummary[]; can_create: boolean; truncated: boolean } | null {
  if (!value || typeof value !== "object") return null;
  const v = value as Record<string, unknown>;
  if (!Array.isArray(v.rooms) || v.rooms.length > 200 || typeof v.can_create !== "boolean" || typeof v.truncated !== "boolean") return null;
  const rooms: RoomSummary[] = [];
  for (const item of v.rooms) {
    if (!item || typeof item !== "object" || typeof item.room_id !== "string" || !/^[a-f0-9]{32}$/.test(item.room_id) ||
      !["lobby", "playing", "awaiting_settlement", "between", "closed"].includes(item.status) ||
      !Array.isArray(item.occupied) || item.occupied.length !== 3 || !item.occupied.every((x: unknown) => typeof x === "boolean") || typeof item.mine !== "boolean") return null;
    rooms.push({ room_id: item.room_id, status: item.status, occupied: item.occupied.slice(), mine: item.mine });
  }
  return { rooms, can_create: v.can_create, truncated: v.truncated };
}
