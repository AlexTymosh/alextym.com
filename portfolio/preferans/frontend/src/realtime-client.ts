/** Bounded, versioned room transport. HTTP remains the only game-command channel. */
import { isRoomView, ROOM_ID_RE, type RoomView } from "./game-model.ru";

import { isMediaEnvelope, parseLiveFrame, type LiveFrame, type LiveSender } from "./live-media-model";

export const REALTIME_PROTOCOL = 1;
export const HEARTBEAT_MS = 15_000;
export const STALE_MS = 38_000;
export type Presence = "online" | "reconnecting" | "offline";

type Frame =
  | { type: "snapshot"; protocol: 1; view: RoomView; presence: Presence[]; server_now_ms: number; live_media?: boolean }
  | { type: "presence"; protocol: 1; presence: Presence[]; server_now_ms: number }
  | { type: "pong"; protocol: 1; server_now_ms: number };

function isPresence(value: unknown): value is Presence[] {
  return Array.isArray(value) && value.length === 3 && value.every(v => ["online", "reconnecting", "offline"].includes(v));
}

export function parseRealtimeFrame(raw: unknown, room: string, seat: number): Frame | null {
  if (typeof raw !== "string" || raw.length > 96_000) return null;
  try {
    const data = JSON.parse(raw) as Record<string, unknown>;
    if (!data || data.protocol !== REALTIME_PROTOCOL || !Number.isSafeInteger(data.server_now_ms)) return null;
    if (data.type === "pong") return data as Frame;
    if (!isPresence(data.presence)) return null;
    if (data.type === "presence") return data as Frame;
    if (data.type === "snapshot" && isRoomView(data.view) && data.view.room_id === room && data.view.my_seat === seat) return data as Frame;
  } catch { /* Invalid peer frame. */ }
  return null;
}

export function retryDelay(attempt: number, fraction = Math.random()): number {
  return Math.min(120_000, 1000 * 2 ** Math.min(Math.max(0, attempt), 7)) * (0.8 + 0.2 * fraction);
}

function validSocketUrl(value: unknown, room: string): string | null {
  if (typeof value !== "string" || value.length > 2048) return null;
  try {
    const url = new URL(value);
    const local = ["localhost", "127.0.0.1"].includes(url.hostname);
    if (!(url.protocol === "wss:" || (url.protocol === "ws:" && local && window.location.protocol === "http:")) ||
      url.username || url.password || url.search || url.hash || url.pathname !== `/api/preferans/rooms/${room}/realtime`) return null;
    return url.href;
  } catch { return null; }
}

export type RealtimeCallbacks = {
  onView: (view: RoomView) => void;
  onClock?: (at: number) => void;
  onReady: (ready: boolean) => void;
  onPresence: (value: Presence[]) => void;
  onDenied: () => void;
  onMediaTransport?: (sender: LiveSender | null) => void;
  onMediaFrame?: (frame: LiveFrame) => void;
};

/** One socket, one heartbeat and one retry per mounted room. No tokens in URLs. */
export function connectRealtime(room: string, seat: number, callbacks: RealtimeCallbacks): () => void {
  if (!ROOM_ID_RE.test(room) || ![0, 1, 2].includes(seat)) return () => undefined;
  let disposed = false;
  let denied = false;
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let startup: ReturnType<typeof setTimeout> | undefined;
  let abort: AbortController | null = null;
  let attempts = 0;
  let lastSeen = 0;
  let latestVersion = -1;
  let mediaBound = false;
  const releaseMedia = () => { if (mediaBound) callbacks.onMediaTransport?.(null); mediaBound = false; };
  const stopTimers = () => {
    if (heartbeat) clearInterval(heartbeat);
    if (startup) clearTimeout(startup);
    heartbeat = undefined; startup = undefined;
  };
  function failAccess() {
    denied = true;
    callbacks.onReady(false);
    callbacks.onDenied();
  }
  function schedule() {
    if (disposed || denied || retry) return;
    callbacks.onReady(false);
    retry = setTimeout(() => { retry = undefined; void start(); }, retryDelay(attempts++));
  }
  async function start() {
    if (disposed || denied || socket) return;
    abort = new AbortController();
    const controller = abort;
    const timeout = setTimeout(() => controller.abort(), 25_000);
    try {
      const response = await fetch(`/api/preferans/rooms/${room}/realtime-ticket`, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: "{}", signal: controller.signal,
      });
      if (disposed) return;
      if ([401, 403].includes(response.status)) { failAccess(); return; }
      if (response.status === 404) { callbacks.onReady(false); return; }
      if (!response.ok) { schedule(); return; }
      const data = await response.json() as Record<string, unknown>;
      const url = validSocketUrl(data.ws_url, room);
      if (!url || data.protocol !== REALTIME_PROTOCOL || typeof data.ticket !== "string" || !/^[A-Za-z0-9_-]{32,128}$/.test(data.ticket)) { schedule(); return; }
      if (disposed) return;
      const token = data.ticket;
      const ws = new WebSocket(url);
      socket = ws;
      latestVersion = -1;
      startup = setTimeout(() => ws.close(), 12_000);
      ws.onopen = () => {
        if (disposed || socket !== ws) { ws.close(); return; }
        lastSeen = Date.now();
        ws.send(JSON.stringify({ type: "authenticate", protocol: REALTIME_PROTOCOL, ticket: token }));
        heartbeat = setInterval(() => {
          if (disposed || socket !== ws) return;
          if (Date.now() - lastSeen > STALE_MS || ws.readyState !== WebSocket.OPEN) { ws.close(); return; }
          try { ws.send(JSON.stringify({ type: "ping", protocol: REALTIME_PROTOCOL })); }
          catch { ws.close(); }
        }, HEARTBEAT_MS);
      };
      ws.onmessage = event => {
        if (disposed || socket !== ws) return;
        if (isMediaEnvelope(event.data)) {
          // Optional channel cannot cause a game socket disconnect on a bad payload.
          const media = parseLiveFrame(event.data, seat);
          if (mediaBound && media) callbacks.onMediaFrame?.(media);
          return;
        }
        const frame = parseRealtimeFrame(event.data, room, seat);
        if (!frame) { ws.close(); return; }
        lastSeen = Date.now();
        callbacks.onClock?.(frame.server_now_ms);
        if (frame.type === "snapshot" && frame.view.version >= latestVersion) {
          latestVersion = frame.view.version;
          if (startup) clearTimeout(startup);
          startup = undefined; attempts = 0;
          callbacks.onView(frame.view);
          callbacks.onPresence(frame.presence);
          callbacks.onReady(true);
          if (frame.live_media === true && callbacks.onMediaTransport && !mediaBound) {
            mediaBound = true;
            callbacks.onMediaTransport(message => {
              if (!mediaBound || disposed || socket !== ws || ws.readyState !== WebSocket.OPEN || ws.bufferedAmount > 128_000) return false;
              try { const wire = JSON.stringify({...message, protocol: REALTIME_PROTOCOL}); if (wire.length > 16_384) return false; ws.send(wire); return true; }
              catch { return false; }
            });
          } else if (frame.live_media !== true && mediaBound) releaseMedia();
        } else if (frame.type === "presence") callbacks.onPresence(frame.presence);
      };
      ws.onerror = () => { if (!disposed && socket === ws) ws.close(); };
      ws.onclose = event => {
        if (socket !== ws) return;
        socket = null; stopTimers(); releaseMedia();
        if (disposed) return;
        if ([4401, 4403].includes(event.code)) { failAccess(); return; }
        schedule();
      };
    } catch { if (!disposed) schedule(); }
    finally { clearTimeout(timeout); if (abort === controller) abort = null; }
  }
  void start();
  return () => {
    releaseMedia();
    disposed = true;
    if (retry) clearTimeout(retry);
    stopTimers(); abort?.abort();
    if (socket) { const ws = socket; socket = null; ws.close(); }
  };
}
