import { ROOM_ROOT } from "../room-transport";
export class RoomRequestError extends Error {
  constructor(public readonly status: number, public readonly code: string) { super(code); }
}
export async function roomRequest<T>(path: string, payload?: object, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${ROOM_ROOT}/api/${path}`, {
    method: payload === undefined ? "GET" : "POST", credentials: "same-origin", cache: "no-store", referrerPolicy: "no-referrer", signal,
    ...(payload === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) throw new RoomRequestError(response.status, typeof data?.detail === "string" ? data.detail : "UNAVAILABLE");
  return data as T;
}
export type Role = "designer" | "moderator" | "dj" | "organizer" | "inviter";
export const ROLES: Role[] = ["designer", "moderator", "dj", "organizer", "inviter"];
export type Interior = "apartment" | "garage" | "beach" | "kindergarten_boat" | "card_club";
export const INTERIORS: Interior[] = ["apartment", "garage", "beach", "kindergarten_boat", "card_club"];
export type RoomSummary = { id: string; slug: string; name: string; capacity: number; status: "active" | "archived"; version: number; is_owner: boolean };
export type Room = RoomSummary & { interior: Interior; roles: Role[]; can_invite: boolean; can_moderate: boolean; members?: { uid: string; roles: Role[]; status: string; owner: boolean }[]; invites?: { id: string; expires_at_ms: number; status: string }[]; transfer?: { id: string; target: string; expires_at_ms: number }; invitation_token?: string };
export type Limits = { storage_rooms: number; active_rooms: number; active_participants: number; capacity_ceiling: number };
export type Identity = { uid: string; can_create: boolean; platform_owner: boolean; limits: Limits };
export type Catalogue = { rooms: RoomSummary[]; uid: string; can_create: boolean; platform_owner: boolean };
