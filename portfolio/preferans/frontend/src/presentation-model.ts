import type { RoomView } from "./game-model.ru";
export type OverlayKind = "score_sheet" | "radio" | "last_trick" | "widow_replay" | "discard_replay";
export type SharedAction = "overlay_open" | "overlay_close" | "break_start" | "break_ready" | "music";
export type Music = { track: number; playing: boolean; offset_ms: number; changed_at_ms: number };
export type Presentation = {
  revision: number; enabled: boolean; server_now_ms: number;
  overlay: null | {kind: OverlayKind; id: number; seat: number; game_id: string|null; opened_at_ms: number};
  break: null | {id: number; ready: boolean[]}; music: Music;
};
export const TRACK_MS=12000;
export const TRACKS=["/preferans/audio/test-01.wav", "/preferans/audio/test-02.wav"] as const;
const int=(x:unknown):x is number=>typeof x==="number"&&Number.isSafeInteger(x)&&x>=0;
export function isPresentation(x:unknown): x is Presentation {
  if (!x || typeof x!=="object") return false;
  const p=x as Presentation;
  return int(p.revision)&&typeof p.enabled==="boolean"&&int(p.server_now_ms)&&
    (p.overlay===null || (!!p.overlay && ["score_sheet","radio","last_trick","widow_replay","discard_replay"].includes(p.overlay.kind)&&int(p.overlay.id)&&p.overlay.id<=p.revision&&[0,1,2].includes(p.overlay.seat)&&int(p.overlay.opened_at_ms)&&(p.overlay.game_id===null||typeof p.overlay.game_id==="string")))&&
    (p.break===null || (!!p.break&&int(p.break.id)&&p.break.id<=p.revision&&Array.isArray(p.break.ready)&&p.break.ready.length===3&&p.break.ready.every(v=>typeof v==="boolean")))&&
    !!p.music&&int(p.music.track)&&p.music.track<TRACKS.length&&typeof p.music.playing==="boolean"&&int(p.music.offset_ms)&&p.music.offset_ms<TRACK_MS&&int(p.music.changed_at_ms);
}
export function replayMoveAllowed(view:RoomView):boolean {
  const reasons=view.controls?.pause_reasons??[];
  return view.presentation?.overlay?.kind==="last_trick"&&reasons.length===1&&reasons[0]==="shared_overlay"&&!view.controls?.undo&&["play","opening_lead"].includes(view.phase??"");
}
export function musicPosition(m:Music,now:number){
  const offset=m.offset_ms+(m.playing?Math.max(0,now-m.changed_at_ms):0);
  return {track:(m.track+Math.floor(offset/TRACK_MS))%TRACKS.length,offset:offset%TRACK_MS};
}
