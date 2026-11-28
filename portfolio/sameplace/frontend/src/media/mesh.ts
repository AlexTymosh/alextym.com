import { emptyView, type MediaProvider, type MediaView, type MediaFrame, type MediaState, type Peer, type Send, type Signal, type TrackKind } from "./types";

type Link = { spec: Peer; pc: RTCPeerConnection; remote: MediaStream; queue: Promise<void>; candidates: RTCIceCandidateInit[]; negotiated: boolean; closed: boolean; bytes: number; timestamp: number; loss: number };

/** Fixed audio/video transceivers avoid renegotiation when users toggle tracks.
 * A single server-assigned offerer per pair avoids glare. ICE can precede SDP.
 * No media stream, SDP or device metadata is sent to Firestore or analytics. */
export class MeshProvider implements MediaProvider {
  private send: Send | null = null;
  private view = emptyView();
  private links = new Map<string,Link>();
  private tracks = new Map<TrackKind,MediaStreamTrack>();
  private pending = new Set<TrackKind>();
  private generation=0;
  private ended=false;
  private timer: ReturnType<typeof setInterval> | null=null;
  private sampling=false;
  constructor(private publish:(view:MediaView)=>void) {}
  private emit() {if(!this.ended)this.publish({...this.view,remote:{...this.view.remote},connections:{...this.view.connections}});}
  private error(code:string) {this.view.status=code;this.emit();}
  transport(send:Send|null){if(this.send===send)return;this.reset();this.send=send;if(send)this.emit();}
  private transmit(frame:object):boolean {return !!this.send?.(frame);}
  join(){if(!this.view.state||this.view.state.occupied)return;this.view.status="";if(!this.transmit({type:"media.join"}))this.error("MEDIA_UNAVAILABLE");}
  leave(){this.transmit({type:"media.leave"});const state=this.view.state;this.reset();if(state){this.view.state={...state,joined:false,peers:[]};this.emit();}}
  mode(mode:MediaState["mode"]){this.transmit({type:"media.mode",mode});}
  moderate(target:string,muted:boolean){this.transmit({type:"media.mute",target,muted});}
  private reset(){this.generation++;this.pending.clear();for(const track of Array.from(this.tracks.values()))track.stop();this.tracks.clear();for(const link of Array.from(this.links.values()))this.close(link);this.links.clear();if(this.timer)clearInterval(this.timer);this.timer=null;this.view=emptyView();this.emit();}
  dispose(){this.ended=true;this.send=null;this.reset();}
  private close(link:Link){link.closed=true;link.pc.ontrack=null;link.pc.onicecandidate=null;link.pc.onconnectionstatechange=null;link.pc.close();for(const track of link.remote.getTracks())track.stop();}
  private stop(kind:TrackKind){const track=this.tracks.get(kind);if(track){this.tracks.delete(kind);track.stop();}this.refreshLocal();for(const link of Array.from(this.links.values()))this.enqueue(link,()=>this.attach(link));}
  private refreshLocal(){this.view.local=this.tracks.size?new MediaStream(Array.from(this.tracks.values())):null;this.view.microphone=this.tracks.has("audio");this.view.camera=this.tracks.has("video");this.transmit({type:"media.tracks",microphone:this.view.microphone,camera:this.view.camera});this.emit();}
  async toggle(kind:TrackKind,deviceId?:string){
    if(!this.view.state?.joined||this.pending.has(kind)||(kind==="audio"&&this.view.state.muted))return;
    if(this.tracks.has(kind)){this.stop(kind);return;}
    const generation=this.generation;this.pending.add(kind);
    try{
      if(!navigator.mediaDevices?.getUserMedia||typeof RTCPeerConnection==="undefined")throw new Error("unsupported");
      const selected=deviceId?{deviceId:{exact:deviceId}}:{};
      const stream=await navigator.mediaDevices.getUserMedia(kind==="audio"?{audio:{...selected,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false}:{audio:false,video:{...selected,width:{ideal:640,max:640},height:{ideal:360,max:360},frameRate:{ideal:15,max:15}}});
      if(this.ended||generation!==this.generation||!this.view.state?.joined||(kind==="audio"&&this.view.state.muted)){stream.getTracks().forEach(track=>track.stop());return;}
      const track=stream.getTracks().find(t=>t.kind===kind);if(!track){stream.getTracks().forEach(t=>t.stop());throw new Error("missing track");}
      stream.getTracks().filter(t=>t!==track).forEach(t=>t.stop());
      this.tracks.set(kind,track);track.onended=()=>{if(this.tracks.get(kind)===track)this.stop(kind);};this.view.status="";this.refreshLocal();for(const link of Array.from(this.links.values()))this.enqueue(link,()=>this.attach(link));
    }catch{if(generation===this.generation&&!this.ended)this.error("MEDIA_DEVICE_UNAVAILABLE");}
    finally{if(generation===this.generation)this.pending.delete(kind);}
  }
  receive(frame:MediaFrame){if(this.ended||!this.send)return;if(frame.type==="media.disabled"){this.reset();return;}if(frame.type==="media.error"){this.error(frame.code);return;}if(frame.type==="media.state"){
      if(this.view.state&&this.view.state.meeting_id!==frame.meeting_id)this.reset();
      if(!frame.joined&&this.view.state?.joined)this.reset();this.view.state=frame;
      if(frame.muted&&this.tracks.has("audio"))this.stop("audio");
      const allowed=new Map(frame.peers.map(p=>[p.id,p]));
      for(const [id,link] of Array.from(this.links.entries())){const spec=allowed.get(id);if(!frame.joined||!spec||spec.pair!==link.spec.pair){this.close(link);this.links.delete(id);delete this.view.remote[id];delete this.view.connections[id];}else link.spec=spec;}
      if(frame.joined){for(const spec of frame.peers)if(!this.links.has(spec.id)){try{this.add(spec,frame.ice_servers);}catch{this.error("MEDIA_UNAVAILABLE");}}if(!this.timer)this.timer=setInterval(()=>void this.sample(),1500);}
      else if(this.timer){clearInterval(this.timer);this.timer=null;}
      this.emit();return;
    }
    const link=this.links.get(frame.from);if(!link||link.spec.pair!==frame.pair)return;this.enqueue(link,()=>this.signal(link,frame.signal));
  }
  private enqueue(link:Link,work:()=>Promise<void>){link.queue=link.queue.then(async()=>{if(!link.closed)await work();}).catch(()=>{if(!link.closed)this.error("MEDIA_CONNECTION_FAILED");});}
  private relay(link:Link,signal:Signal){if(!link.closed&&!this.transmit({type:"media.signal",target:link.spec.id,pair:link.spec.pair,signal}))this.error("MEDIA_UNAVAILABLE");}
  private add(spec:Peer,iceServers:RTCIceServer[]){
    const pc=new RTCPeerConnection({iceServers,iceTransportPolicy:"all"});
    const link:Link={spec,pc,remote:new MediaStream(),queue:Promise.resolve(),candidates:[],negotiated:false,closed:false,bytes:0,timestamp:0,loss:0};
    this.links.set(spec.id,link);this.view.connections[spec.id]="connecting";
    pc.onicecandidate=event=>{const c=event.candidate;if(c?.candidate)this.relay(link,{kind:"ice",candidate:c.candidate,sdpMid:c.sdpMid,sdpMLineIndex:c.sdpMLineIndex});};
    pc.onconnectionstatechange=()=>{if(link.closed)return;this.view.connections[spec.id]=pc.connectionState;if(pc.connectionState==="failed")this.view.status="MEDIA_CONNECTION_FAILED";this.emit();};
    pc.ontrack=event=>{if(link.closed)return;if(!link.remote.getTracks().includes(event.track))link.remote.addTrack(event.track);this.view.remote[spec.id]=link.remote;this.emit();};
    if(spec.offerer){pc.addTransceiver("audio",{direction:"sendrecv"});pc.addTransceiver("video",{direction:"sendrecv"});this.enqueue(link,async()=>{await this.attach(link);const offer=await pc.createOffer();await pc.setLocalDescription(offer);if(offer.sdp)this.relay(link,{kind:"offer",sdp:offer.sdp});});}
  }
  private async attach(link:Link){for(const transceiver of link.pc.getTransceivers()){
    const kind=transceiver.receiver.track.kind as TrackKind;const track=this.tracks.get(kind)??null;
    if(kind==="audio"||kind==="video")await transceiver.sender.replaceTrack(track);
    if(kind==="video"&&track){const params=transceiver.sender.getParameters();if(params.encodings.length){params.encodings[0].maxBitrate=300000;params.encodings[0].maxFramerate=15;await transceiver.sender.setParameters(params).catch(()=>undefined);}}
  }}
  private async signal(link:Link,signal:Signal){const pc=link.pc;
    if(signal.kind==="ice"){const candidate={candidate:signal.candidate,sdpMid:signal.sdpMid,sdpMLineIndex:signal.sdpMLineIndex};if(!pc.remoteDescription){if(link.candidates.length<96)link.candidates.push(candidate);return;}await pc.addIceCandidate(candidate);return;}
    if(link.negotiated||signal.kind==="offer"&&link.spec.offerer||signal.kind==="answer"&&!link.spec.offerer)return;
    await pc.setRemoteDescription({type:signal.kind,sdp:signal.sdp});for(const candidate of link.candidates.splice(0))await pc.addIceCandidate(candidate);
    if(signal.kind==="offer"){for(const transceiver of pc.getTransceivers())transceiver.direction="sendrecv";await this.attach(link);const answer=await pc.createAnswer();await pc.setLocalDescription(answer);if(answer.sdp)this.relay(link,{kind:"answer",sdp:answer.sdp});}link.negotiated=true;
  }
  private async sample(){if(this.sampling||!this.view.state?.joined)return;this.sampling=true;const generation=this.generation;let speaking=false,rtt:number|null=null,loss=0,kbps=0;
    try{for(const link of Array.from(this.links.values())){if(link.closed)continue;const report: RTCStatsReport=await link.pc.getStats();let bytes=0,stamp=0,packets=0;report.forEach(stat=>{if(stat.type==="inbound-rtp"){bytes+=Number(stat.bytesReceived)||0;stamp=Math.max(stamp,Number(stat.timestamp)||0);packets+=Math.max(0,Number(stat.packetsLost)||0);if(!link.spec.muted&&stat.kind==="audio"&&Number(stat.audioLevel)>0.025)speaking=true;}if(stat.type==="media-source"&&stat.kind==="audio"&&Number(stat.audioLevel)>0.025)speaking=true;if(stat.type==="candidate-pair"&&stat.state==="succeeded"&&stat.nominated&&Number.isFinite(stat.currentRoundTripTime))rtt=Math.round(1000*stat.currentRoundTripTime);});if(link.timestamp&&stamp>link.timestamp)kbps+=Math.max(0,(bytes-link.bytes)*8/(stamp-link.timestamp));link.bytes=bytes;link.timestamp=stamp;link.loss=packets;loss+=packets;}if(generation===this.generation&&!this.ended){this.view.speaking=speaking;this.view.stats={rttMs:rtt,loss,inboundKbps:Math.round(kbps)};this.emit();}}catch{/* Diagnostics cannot break conversation. */}finally{this.sampling=false;}
  }
}
