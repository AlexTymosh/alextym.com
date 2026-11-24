/** Strict ephemeral media signalling contract, separate from game commands. */
export type MediaKind = "audio" | "video";
export type Participant = { session: string; audio: boolean; video: boolean };
export type MediaRoster = Array<Participant | null>;
export type LiveSignalKind = "offer" | "answer" | "ice";
export type LiveFrame =
  | { type: "media_state"; participants: MediaRoster }
  | { type: "media_signal"; from: number; from_session: string; to_session: string; kind: LiveSignalKind; data: RTCSessionDescriptionInit | RTCIceCandidateInit }
  | { type: "media_error" };
export type LiveCommand =
  | { type: "media_join" | "media_leave" }
  | { type: "media_presence"; audio: boolean; video: boolean }
  | { type: "media_signal"; to: number; to_session: string; kind: LiveSignalKind; data: RTCSessionDescriptionInit | RTCIceCandidateInit };
export type LiveSender = (message: LiveCommand) => boolean;
export const emptyRoster = (): MediaRoster => [null, null, null];
const session = (x: unknown): x is string => typeof x === "string" && /^[a-f0-9]{32}$/.test(x);
function object(x: unknown): x is Record<string, unknown> { return !!x && typeof x === "object" && !Array.isArray(x); }
export function parseLiveFrame(raw: string, seat: number): LiveFrame | null {
  if (raw.length > 96_000) return null;
  try {
    const f: unknown = JSON.parse(raw);
    if (!object(f) || f.protocol !== 1 || !Number.isSafeInteger(f.server_now_ms)) return null;
    if (f.type === "media_error") return { type: "media_error" };
    if (f.type === "media_state" && Array.isArray(f.participants) && f.participants.length === 3 && f.participants.every(p => p === null || (object(p) && session(p.session) && typeof p.audio === "boolean" && typeof p.video === "boolean"))) {
      return { type: "media_state", participants: f.participants.map(p => p === null ? null : {session:p.session,audio:p.audio,video:p.video}) };
    }
    if (f.type !== "media_signal" || typeof f.from !== "number" || ![0,1,2].includes(f.from) || f.from === seat || !session(f.from_session) || !session(f.to_session) || !object(f.data)) return null;
    const base = { type: "media_signal" as const, from: f.from, from_session: f.from_session, to_session:f.to_session };
    const d = f.data;
    if ((f.kind === "offer" || f.kind === "answer") && d.type === f.kind && typeof d.sdp === "string" && d.sdp.length > 0 && d.sdp.length <= 12000) return {...base, kind:f.kind, data:{type:f.kind,sdp:d.sdp}};
    if (f.kind === "ice" && typeof d.candidate === "string" && d.candidate.length > 0 && d.candidate.length <= 2048 && (d.sdpMid == null || typeof d.sdpMid === "string") && (d.usernameFragment == null || typeof d.usernameFragment === "string") && (d.sdpMLineIndex == null || (typeof d.sdpMLineIndex === "number" && Number.isInteger(d.sdpMLineIndex) && d.sdpMLineIndex >= 0 && d.sdpMLineIndex <= 16))) return {...base,kind:"ice",data:{candidate:d.candidate,sdpMid:d.sdpMid as string | null | undefined,sdpMLineIndex:d.sdpMLineIndex as number | null | undefined,usernameFragment:d.usernameFragment as string | null | undefined}};
  } catch { /* Reject malformed frames. */ }
  return null;
}
export function isMediaEnvelope(raw: unknown): raw is string {
  if (typeof raw !== "string" || raw.length > 96_000) return false;
  try { const x: unknown = JSON.parse(raw); return object(x) && typeof x.type === "string" && x.type.startsWith("media_"); }
  catch { return false; }
}
