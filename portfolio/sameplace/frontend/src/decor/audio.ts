import type {MusicState,Source} from "./types";

export function targetPosition(state:MusicState,source:Source,now:number):number {
  if(!source.duration_ms)return 0;
  const elapsed=state.playback==="playing"?Math.max(0,now-state.started_at_ms):0;
  return ((state.position_ms+elapsed)%source.duration_ms)/1000;
}
// Original procedural demo tones; no downloaded recordings or third-party composition.
export function demoWave(id:string):Blob {
  if(id!=="test_disco"&&id!=="test_retro")throw new Error("Unknown audio fixture");
  const rate=16000, size=rate*8, buffer=new ArrayBuffer(44+size*2), view=new DataView(buffer);
  const text=(offset:number,value:string)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
  text(0,"RIFF");view.setUint32(4,36+size*2,true);text(8,"WAVE");text(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,"data");view.setUint32(40,size*2,true);
  const notes=id==="test_disco"?[110,110,164.81,130.81,110,146.83,130.81,164.81]:[130.81,164.81,196,146.83,130.81,174.61,146.83,110];
  for(let i=0;i<size;i++){const time=i/rate,beat=Math.floor(time*4),phase=time*4-beat,frequency=notes[beat%notes.length],envelope=Math.min(1,phase*18)*Math.pow(1-phase,2);const sample=(Math.sin(2*Math.PI*frequency*time)*.23+Math.sin(4*Math.PI*frequency*time)*.07)*envelope;view.setInt16(44+i*2,Math.round(sample*32767),true);}
  return new Blob([buffer],{type:"audio/wav"});
}
