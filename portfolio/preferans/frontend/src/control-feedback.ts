import type { RoomView } from "./game-model.ru";

export const TABLE_ZOOM_MIN = 70;
export const TABLE_ZOOM_MAX = 130;
export const TABLE_ZOOM_STEP = 10;
export const FEEDBACK_MS = 12_000;

export function tableZoomValue(value: unknown): number {
  if (typeof value !== "number" && (typeof value !== "string" || !value.trim())) return 100;
  const n = Number(value);
  if (!Number.isFinite(n)) return 100;
  return Math.max(TABLE_ZOOM_MIN, Math.min(TABLE_ZOOM_MAX, Math.round(n / TABLE_ZOOM_STEP) * TABLE_ZOOM_STEP));
}

export function canRequestUndo(view: RoomView): boolean {
  return view.status === "playing" && view.my_seat !== null && Boolean(view.controls?.can_request_undo) &&
    !view.controls?.counter && !view.controls?.paused && !view.controls?.undo && view.claim?.status !== "pending";
}

export function showFirstHand(view: RoomView, seat: number): boolean {
  return view.status === "playing" && view.first_hand === seat && (view.played_tricks ?? 0) === 0 && !view.trick?.length;
}

export function feedbackRemaining(at: number, now: number): number {
  return Number.isFinite(at) && now - at <= 300_000 ? FEEDBACK_MS : 0;
}
