import { roomRequest, RoomRequestError } from "../rooms/client";
import type { Snapshot } from "./types";
import { parseMedia, type MediaFrame, type Send } from "../media/types";
export type ConnectionStatus = "connecting" | "online" | "waiting" | "degraded" | "disabled";
type Ticket = { ticket: string; ws_url: string; protocol_version: number };
const tokenPattern = /^[A-Za-z0-9_-]{43}$/;
function validSnapshot(value: unknown): value is Snapshot {
  if (!value || typeof value !== "object") return false;
  const v = value as Snapshot;
  return v.type === "room.snapshot" && v.protocol_version === 1 && typeof v.meeting_id === "string" && typeof v.room_id === "string" && Number.isSafeInteger(v.sequence) && Number.isSafeInteger(v.chat_revision) && Number.isSafeInteger(v.room_revision) && Number.isSafeInteger(v.inbox_revision) && Array.isArray(v.people) && v.people.length <= 10 && Array.isArray(v.proposals) && v.proposals.length <= 8;
}
export function openMeeting(slug: string, roomId: string, handlers: { snapshot: (value: Snapshot) => void; status: (status: ConnectionStatus, code?: string) => void; denied: () => void; media?: (frame: MediaFrame) => void; transport?: (send: Send | null) => void }): () => void {
  let stopped = false, attempts = 0, socket: WebSocket | undefined;
  let retry: ReturnType<typeof setTimeout> | undefined, heartbeat: ReturnType<typeof setInterval> | undefined;
  let connectDeadline: ReturnType<typeof setTimeout> | undefined;
  let request: AbortController | undefined;
  let lastPong = 0;
  function clearSocket() {
    if (heartbeat) clearInterval(heartbeat);
    if (connectDeadline) clearTimeout(connectDeadline);
    heartbeat = undefined; connectDeadline = undefined;
    const old = socket; socket = undefined;
    handlers.transport?.(null);
    if (old) { old.onopen = null; old.onmessage = null; old.onclose = null; old.onerror = null; old.close(); }
  }
  function schedule(status: ConnectionStatus, code?: string, minimumSeconds=0) {
    if (stopped) return;
    handlers.status(status, code);
    clearSocket();
    if (retry) clearTimeout(retry);
    const delay = Math.max(minimumSeconds*1000, document.visibilityState === "hidden" ? 60000 : 15000, Math.min(120000, 15000 * 2 ** Math.min(attempts++, 3)));
    retry = setTimeout(() => void connect(), delay + Math.floor(Math.random() * 2000));
  }
  async function connect() {
    if (stopped) return;
    handlers.status("connecting"); request = new AbortController();
    try {
      const ticket = await roomRequest<Ticket>(`rooms/${slug}/ticket`, { origin: window.location.origin }, request.signal);
      if (stopped) return;
      const url = new URL(ticket.ws_url);
      if (ticket.protocol_version !== 1 || !tokenPattern.test(ticket.ticket) || url.pathname !== "/api/sameplace/realtime" || url.search || url.hash || url.username || url.password || !["wss:", "ws:"].includes(url.protocol) || (url.protocol === "ws:" && !["localhost", "127.0.0.1"].includes(url.hostname))) throw new Error("Invalid realtime endpoint");
      const current = socket = new WebSocket(url);
      let lastMeeting = "", lastSequence = -1, lastInbox = -1;
      let lastError = "";
      connectDeadline = setTimeout(() => { if (socket === current) schedule("degraded"); }, 20000);
      current.onopen = () => { if (socket === current) current.send(JSON.stringify({ type: "auth", ticket: ticket.ticket })); };
      current.onmessage = event => {
        if (stopped || socket !== current || typeof event.data !== "string" || event.data.length > 100000) return;
        try {
          const data: unknown = JSON.parse(event.data);
          if (validSnapshot(data) && data.room_id === roomId) {
            if (data.meeting_id === lastMeeting && (data.sequence < lastSequence || (data.sequence === lastSequence && data.inbox_revision === lastInbox))) return;
            lastMeeting = data.meeting_id; lastSequence = data.sequence; lastInbox = data.inbox_revision;
            if (connectDeadline) { clearTimeout(connectDeadline); connectDeadline = undefined; }
            if (!heartbeat) {
              handlers.transport?.(frame => {
                if (stopped || socket !== current || current.readyState !== WebSocket.OPEN || current.bufferedAmount > 262144) return false;
                const message = JSON.stringify(frame);
                if (new TextEncoder().encode(message).length > 32768) return false;
                current.send(message); return true;
              });
              lastPong = Date.now();
              heartbeat = setInterval(() => {
                if (socket !== current) return;
                if (Date.now() - lastPong > 65000) { schedule("degraded"); return; }
                if (current.readyState === WebSocket.OPEN) current.send(JSON.stringify({type: "ping"}));
              }, 25000);
            }
            attempts = 0; handlers.status("online"); handlers.snapshot(data);
          } else if (data && typeof data === "object" && "type" in data) {
            if (lastMeeting) { const media = parseMedia(data,lastMeeting); if (media) handlers.media?.(media); }
            if (data.type === "pong") lastPong = Date.now();
            if (data.type === "error" && "code" in data && typeof data.code === "string") lastError = data.code;
          }
        } catch { schedule("degraded"); }
      };
      current.onclose = () => {
        if (stopped || socket !== current) return;
        if (["REALTIME_REVOKED", "ROOM_NOT_FOUND", "ACCESS_DENIED", "AUTH_REQUIRED"].includes(lastError)) { clearSocket(); handlers.denied(); return; }
        schedule(["WAIT_CAPACITY", "OTHER_MEETING", "TAB_LIMIT"].includes(lastError) ? "waiting" : "degraded", lastError);
      };
      current.onerror = () => { if (socket === current && current.readyState === WebSocket.CLOSED) schedule("degraded"); };
    } catch (cause) {
      if (stopped) return;
      if (cause instanceof RoomRequestError) {
        if ([401,404].includes(cause.status)) { handlers.denied(); return; }
        if (cause.code === "REALTIME_DISABLED") { handlers.status("disabled", cause.code); return; }
        if (cause.status === 403) { handlers.denied(); return; }
      }
      schedule("degraded", undefined, cause instanceof RoomRequestError ? cause.retryAfterSeconds : 0);
    }
  }
  queueMicrotask(() => { if (!stopped) void connect(); });
  return () => { stopped = true; request?.abort(); if (retry) clearTimeout(retry); clearSocket(); };
}
