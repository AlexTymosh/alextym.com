import { ROOM_ID_RE, type CommandAction, type RoomInvitation, type RoomView, isInvitation, isRoomView } from "./game-model.ru";

import { gameCooldown } from "./transport-budget";

export class ApiError extends Error {
  constructor(readonly status: number, message: string) { super(message); this.name = "ApiError"; Object.setPrototypeOf(this, ApiError.prototype); }
}

type AnyResponse = Record<string, unknown>;
const prefix = "/api/preferans/rooms";
const timeoutMs = 30_000;

async function request(path: string, method: "GET" | "POST", payload?: object): Promise<unknown> {
  if (gameCooldown.remaining()) throw new ApiError(503, "Game service cooling down");
  const response = await fetch(prefix + path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json", ...(payload ? { "Content-Type": "application/json" } : {}) },
    body: payload ? JSON.stringify(payload) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    gameCooldown.observe(response.status, response.headers.get("Retry-After"));
    throw new ApiError(response.status, "Game API request failed");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new ApiError(502, "Invalid API response");
  return body;
}

function path(roomId: string, suffix: string): string {
  if (!ROOM_ID_RE.test(roomId)) throw new ApiError(422, "Invalid room ID");
  return `/${roomId}/${suffix}`;
}
function assertMutation(value: unknown): { room_id: string; version: number; status: string } {
  const data = value as AnyResponse;
  if (!data || typeof data.room_id !== "string" || !ROOM_ID_RE.test(data.room_id) ||
      !Number.isSafeInteger(data.version) || typeof data.status !== "string") {
    throw new ApiError(502, "Invalid mutation response");
  }
  return { room_id: data.room_id, version: data.version as number, status: data.status };
}
export const newKey = () => crypto.randomUUID();
export async function createRoom(token: string) {
  return assertMutation(await request("", "POST", { idempotency_key: token }));
}
export async function invitation(roomId: string): Promise<RoomInvitation> {
  const data = await request(path(roomId, "invitation"), "GET");
  if (!isInvitation(data)) throw new ApiError(502, "Invalid invitation");
  return data;
}
export async function roomView(roomId: string, sinceVersion?: number): Promise<RoomView | { unchanged: true; version: number }> {
  const query = Number.isSafeInteger(sinceVersion) && (sinceVersion as number) >= 0
    ? `?since_version=${sinceVersion}` : "";
  const value = await request(path(roomId, "view") + query, "GET");
  const data = value as Record<string, unknown>;
  if (data.unchanged === true && data.room_id === roomId && Number.isSafeInteger(data.version)) {
    return { unchanged: true, version: data.version as number };
  }
  if (!isRoomView(value)) throw new ApiError(502, "Invalid room view");
  return value;
}
export async function joinRoom(roomId: string, token: string, version: number) {
  return assertMutation(await request(path(roomId, "join"), "POST", { idempotency_key: token, expected_version: version }));
}
export async function startRoom(roomId: string, token: string, version: number) {
  return assertMutation(await request(path(roomId, "start"), "POST", { idempotency_key: token, expected_version: version }));
}
export async function sendCommand(roomId: string, token: string, version: number, action: CommandAction, args: Record<string, unknown>) {
  return assertMutation(await request(path(roomId, "commands"), "POST", {
    idempotency_key: token, expected_version: version, action, args,
  }));
}
export async function settleRoom(roomId: string, token: string, version: number, regularRoute: "pool" | "hill_first", passoutRoutes: Array<"pool" | "hill_first" | "help">) {
  if (passoutRoutes.length !== 3) throw new ApiError(422, "Invalid passout routes");
  return assertMutation(await request(path(roomId, "settle"), "POST", {
    idempotency_key: token, expected_version: version,
    regular_route: regularRoute, passout_routes: passoutRoutes,
  }));
}

export async function adjustRoom(roomId: string, token: string, version: number,
  adjustment: { field: "pool" | "hill" | "vist"; seat: number; against: number | null; delta: number; reason: string }) {
  return assertMutation(await request(path(roomId, "adjust"), "POST", {
    idempotency_key: token, expected_version: version, ...adjustment,
  }));
}
