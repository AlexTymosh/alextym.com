/** Server-only, seat-scoped signalling. No media uploads, credentials or Firestore SDK. */
import { ROOM_ID_RE } from "./game-model.ru";

export type MediaPresence = { audio: boolean; video: boolean };
export type MediaSignal = {
  sequence: number; from: number; kind: "offer" | "answer" | "ice" | "restart";
  data: Record<string, unknown>;
};
export type MediaRecording = {
  id: string; initiator: number; status: "requested" | "ready" | "active" | "stopped";
  votes: Array<boolean | null>;
};
export type MediaState = {
  room_id: string; seat: number; version: number; participants: MediaPresence[];
  signals: MediaSignal[]; recording: MediaRecording | null;
};
export type MediaAction =
  | "presence" | "signal" | "record_request" | "record_vote" | "record_start" | "record_stop";

// Stop recording conservatively when permission cannot be confirmed. This is
// a local safety guard, not a guarantee against a malicious third-party recorder.
export const RECORDING_WATCHDOG_MS = 8_000;
export function recordingMayContinue(
  state: Pick<MediaState, "recording" | "participants"> | null,
  seat: number,
  confirmedAtMs: number,
  nowMs: number,
  visibleAndOnline: boolean,
): boolean {
  if (!visibleAndOnline || !Number.isFinite(confirmedAtMs) || confirmedAtMs <= 0 ||
      !Number.isFinite(nowMs) || nowMs < confirmedAtMs ||
      nowMs - confirmedAtMs > RECORDING_WATCHDOG_MS ||
      state?.recording?.initiator !== seat || state.recording.status !== "active" ||
      state.recording.votes.length !== 3 || !state.recording.votes.every(v => v === true) ||
      state.participants.length !== 3) return false;
  return state.participants.every(p => p.audio || p.video);
}

function route(room: string): string {
  if (!ROOM_ID_RE.test(room)) throw new Error("Invalid room ID");
  return `/api/preferans/rooms/${room}/media`;
}

async function jsonResponse(res: Response): Promise<Record<string, unknown>> {
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(`Media service returned HTTP ${res.status}`);
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Invalid media reply");
  return data as Record<string, unknown>;
}

export function isMediaState(value: unknown, room: string): value is MediaState {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const data = value as Record<string, unknown>;
  if (data.room_id !== room || ![0, 1, 2].includes(data.seat as number) ||
      !Number.isSafeInteger(data.version) || (data.version as number) < 0 ||
      !Array.isArray(data.participants) || data.participants.length !== 3 ||
      !data.participants.every((p: unknown) => p && typeof p === "object" &&
        typeof (p as MediaPresence).audio === "boolean" && typeof (p as MediaPresence).video === "boolean") ||
      !Array.isArray(data.signals) || data.signals.length > 64 ||
      !data.signals.every((s: unknown) => {
        if (!s || typeof s !== "object") return false;
        const m = s as Record<string, unknown>;
        return Number.isSafeInteger(m.sequence) && [0, 1, 2].includes(m.from as number) &&
          ["offer", "answer", "ice", "restart"].includes(String(m.kind)) &&
          m.data !== null && typeof m.data === "object" && !Array.isArray(m.data);
      })) return false;
  if (data.recording === null) return true;
  if (!data.recording || typeof data.recording !== "object") return false;
  const recording = data.recording as Record<string, unknown>;
  return typeof recording.id === "string" && /^[a-f0-9]{24}$/.test(recording.id) &&
    [0, 1, 2].includes(recording.initiator as number) &&
    ["requested", "ready", "active", "stopped"].includes(String(recording.status)) &&
    Array.isArray(recording.votes) && recording.votes.length === 3 &&
    recording.votes.every(v => v === null || typeof v === "boolean");
}

export async function getMedia(room: string, cursor: number): Promise<MediaState> {
  const res = await fetch(`${route(room)}?cursor=${Math.max(0, cursor)}`, {
    credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(20000),
  });
  const data = await jsonResponse(res);
  if (!isMediaState(data, room)) throw new Error("Invalid media view");
  return data;
}

export async function postMedia(
  room: string, action: MediaAction, args: Record<string, unknown> = {}, token = crypto.randomUUID(),
): Promise<void> {
  await jsonResponse(await fetch(route(room), {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ idempotency_key: token, action, args }),
    signal: AbortSignal.timeout(20000),
  }));
}
