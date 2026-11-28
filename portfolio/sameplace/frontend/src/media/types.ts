export type Peer = { id: string; pair: string; offerer: boolean; muted: boolean; microphone: boolean; camera: boolean };
export type MediaState = { type: "media.state"; meeting_id: string; mode: "room" | "location"; joined: boolean; occupied: boolean; muted: boolean; peers: Peer[]; ice_servers: RTCIceServer[] };
export type Signal = { kind: "offer" | "answer"; sdp: string } | { kind: "ice"; candidate: string; sdpMid: string | null; sdpMLineIndex: number | null };
export type MediaFrame = MediaState | { type: "media.signal"; from: string; pair: string; signal: Signal } | { type: "media.error"; code: string } | { type: "media.disabled" };
export type Send = (frame: object) => boolean;
export type TrackKind = "audio" | "video";
export type MediaView = { state: MediaState | null; local: MediaStream | null; remote: Record<string, MediaStream>; microphone: boolean; camera: boolean; speaking: boolean; status: string; connections: Record<string, string>; stats: { rttMs: number | null; loss: number; inboundKbps: number } };
export interface MediaProvider {
  transport(send: Send | null): void;
  receive(frame: MediaFrame): void;
  join(): void;
  leave(): void;
  toggle(kind: TrackKind, deviceId?: string): Promise<void>;
  mode(mode: MediaState["mode"]): void;
  moderate(target: string, muted: boolean): void;
  dispose(): void;
}
export const emptyView = (): MediaView => ({state:null,local:null,remote:{},microphone:false,camera:false,speaking:false,status:"",connections:{},stats:{rttMs:null,loss:0,inboundKbps:0}});
const id = /^[a-f0-9]{32}$/;
export function parseMedia(value: unknown, meetingId: string): MediaFrame | null {
  if (!value || typeof value !== "object") return null;
  const v = value as MediaFrame;
  if (v.type === "media.disabled") return v;
  if (v.type === "media.error" && typeof v.code === "string" && /^MEDIA_[A-Z_]{2,40}$/.test(v.code)) return v;
  if (v.type === "media.state" && v.meeting_id === meetingId && ["room","location"].includes(v.mode) && typeof v.joined === "boolean" && typeof v.occupied === "boolean" && typeof v.muted === "boolean" && Array.isArray(v.peers) && v.peers.length <= 9 && v.peers.every(p=>p && id.test(p.id) && id.test(p.pair) && typeof p.offerer === "boolean" && typeof p.muted === "boolean" && typeof p.microphone === "boolean" && typeof p.camera === "boolean") && new Set(v.peers.map(p=>p.id)).size===v.peers.length && Array.isArray(v.ice_servers) && v.ice_servers.length <= 1 && v.ice_servers.every(s=>s && typeof s.urls === "string" && /^stuns?:[a-zA-Z0-9.-]+(?::[0-9]{1,5})?$/.test(s.urls))) return v;
  if (v.type === "media.signal" && id.test(v.from) && id.test(v.pair) && v.signal && typeof v.signal === "object") {
    const s=v.signal;
    if ((s.kind==="offer"||s.kind==="answer") && typeof s.sdp==="string" && s.sdp.length>0 && s.sdp.length<=24000) return v;
    if(s.kind==="ice" && typeof s.candidate==="string" && s.candidate.length>0 && s.candidate.length<=2048 && (s.sdpMid===null||typeof s.sdpMid==="string"&&s.sdpMid.length<=64) && (s.sdpMLineIndex===null||Number.isInteger(s.sdpMLineIndex)&&s.sdpMLineIndex>=0&&s.sdpMLineIndex<=16)) return v;
  }
  return null;
}
