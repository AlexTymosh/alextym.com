export type AudioPreferences = { voices: number; music: number; ambient: number; game: number; masterMute: boolean; musicMute: boolean; duck: boolean; microphone: string; camera: string; output: string };
export const DEFAULT_AUDIO: AudioPreferences = { voices:85,music:45,ambient:15,game:50,masterMute:false,musicMute:false,duck:true,microphone:"",camera:"",output:"" };
const key="sameplace.audio.v1";
export function normalizeAudio(value: unknown): AudioPreferences {
  const v=(value&&typeof value==="object"?value:{}) as Partial<AudioPreferences>;
  const volume=(x:unknown,fallback:number)=>typeof x==="number"&&Number.isFinite(x)?Math.round(Math.max(0,Math.min(100,x))):fallback;
  const flag=(x:unknown,fallback:boolean)=>typeof x==="boolean"?x:fallback;
  const device=(x:unknown)=>typeof x==="string"&&x.length<=512?x:"";
  return {voices:volume(v.voices,85),music:volume(v.music,45),ambient:volume(v.ambient,15),game:volume(v.game,50),masterMute:flag(v.masterMute,false),musicMute:flag(v.musicMute,false),duck:flag(v.duck,true),microphone:device(v.microphone),camera:device(v.camera),output:device(v.output)};
}
export function loadAudio(): AudioPreferences {try{return normalizeAudio(JSON.parse(localStorage.getItem(key)??"null"));}catch{return {...DEFAULT_AUDIO};}}
export function saveAudio(value: AudioPreferences) {try{localStorage.setItem(key,JSON.stringify(normalizeAudio(value)));}catch{/* private mode / storage disabled */}}
export function musicGain(value: AudioPreferences,speaking:boolean):number {return value.masterMute||value.musicMute?0:value.music/100*(value.duck&&speaking?0.25:1);}

export type AudioBus = "voices" | "music" | "ambient" | "game";
export function busGain(value:AudioPreferences,bus:AudioBus,speaking=false):number {return bus==="music"?musicGain(value,speaking):value.masterMute?0:value[bus]/100;}
