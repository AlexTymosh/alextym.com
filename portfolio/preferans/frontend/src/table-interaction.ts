import type { Card, RoomView } from "./game-model.ru";
import { allowedToAct, cardId } from "./game-model.ru";
import { isCard, validSeat } from "./table-model";

export type BackTheme = "classic" | "ornament" | "red-blue" | "green";
export const backThemes: readonly BackTheme[] = ["classic", "ornament", "red-blue", "green"];
export const isBackTheme = (value: unknown): value is BackTheme => backThemes.includes(value as BackTheme);
export type DragIntent = { kind: "card"; id: string; owner: number; room: string; game: string | null; version: number }
  | { kind: "deck"; room: string; game: string | null; version: number }
  | { kind: "discard"; id: string; room: string; game: string | null; version: number };
export function matchingDrag(drag: DragIntent | null, view: RoomView): boolean {
  return !!drag && drag.room === view.room_id && drag.game === view.game_id && drag.version === view.version;
}
export function legalDrop(view: RoomView, drag: DragIntent | null): Card | null {
  if (!matchingDrag(drag, view) || drag?.kind !== "card" || !allowedToAct(view) ||
    !["play", "opening_lead"].includes(view.phase ?? "") || drag.owner !== view.turn) return null;
  return (view.legal_cards ?? []).find(card => isCard(card) && cardId(card) === drag.id) ?? null;
}
export function dealerFor(view: RoomView): number | null {
  if (view.status === "lobby") return view.lobby_setup?.dealer ?? 2;
  if (view.status === "between" && validSeat(view.dealer)) return (view.dealer + 1) % 3;
  return null;
}
export function mayStart(view: RoomView): boolean {
  const dealer = dealerFor(view);
  return dealer !== null && (view.room_admin || (view.my_seat === dealer && (view.status === "between" || !!view.lobby_setup))) &&
    !view.next_deal && !view.seat_swap && !view.controls?.paused && !view.controls?.undo &&
    view.occupied.every(Boolean) && (!view.lobby_setup || view.lobby_setup.ready.every(Boolean));
}
export function mayPassDeck(view: RoomView, target: number): boolean {
  return view.status === "lobby" && !!view.lobby_setup && view.my_seat === view.lobby_setup.dealer &&
    !view.seat_swap && !view.controls?.paused && validSeat(target) && target !== view.my_seat && view.occupied[target];
}
export function changeDraft(ids: readonly string[], id: string, add: boolean): string[] {
  if (!add) return ids.filter(x => x !== id);
  return ids.includes(id) || ids.length >= 2 ? [...ids] : [...ids, id];
}
export function invitationId(input: string, origin: string): string {
  const raw = input.trim();
  if (/^[a-f0-9]{32}$/.test(raw)) return raw;
  try {
    const url = new URL(raw, origin);
    const id = url.searchParams.get("room") ?? "";
    return url.origin === origin && url.pathname.replace(/\/$/, "") === "/portfolio/preferans" && /^[a-f0-9]{32}$/.test(id) ? id : "";
  } catch { return ""; }
}
