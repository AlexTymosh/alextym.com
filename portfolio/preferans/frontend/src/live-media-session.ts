/** One optional two-peer WebRTC mesh per authenticated room socket.
 * Only explicit join enables receiving; only explicit device actions acquire tracks.
 * All operations and signals are scoped to a peer's current media session.
 */
import { emptyRoster, type LiveCommand, type LiveFrame, type LiveSender, type MediaKind, type MediaRoster, type Participant } from "./live-media-model";

export type LiveState = {
  joining: boolean; joined: boolean; changing: boolean; audio: boolean; video: boolean;
  roster: MediaRoster; streams: Record<number, MediaStream>; connections: Record<number, RTCPeerConnectionState>;
  error: "" | "transport" | "device" | "peer";
};
export const blankLiveState = (): LiveState => ({joining:false, joined:false,changing:false,audio:false,video:false,roster:emptyRoster(),streams:{},connections:{},error:""});
type Peer = { session:string; pc:RTCPeerConnection; pending:RTCIceCandidateInit[]; serial:Promise<void>; incoming:MediaStreamTrack[]; closed:boolean };
const ICE_SERVERS: RTCIceServer[] = [{urls:["stun:stun.l.google.com:19302"]}];

export class LiveMediaSession {
  private state = blankLiveState();
  private readonly peers = new Map<number, Peer>();
  private readonly tracks: Partial<Record<MediaKind, MediaStreamTrack>> = {};
  private desired = false;
  private disposed = false;
  private generation = 0;
  private joiningTimer: ReturnType<typeof setTimeout> | undefined;
  constructor(private readonly seat:number, private readonly send:LiveSender, private readonly changed:(state:LiveState)=>void) {}
  private update(patch:Partial<LiveState>) { this.state={...this.state,...patch}; if(!this.disposed)this.changed(this.state); }
  private transmit(message:LiveCommand):boolean { return !this.disposed && this.send(message); }
  join() {
    if(this.desired || this.disposed) return;
    this.desired=true;
    this.update({joining:true,error:""});
    if(!this.transmit({type:"media_join"})) { this.reset("transport"); return; }
    this.joiningTimer=setTimeout(()=>{if(this.desired&&!this.state.joined){this.transmit({type:"media_leave"});this.reset("transport");}},8000);
  }
  leave() { if(this.desired)this.transmit({type:"media_leave"});this.reset(""); }
  dispose() { if(this.desired)this.transmit({type:"media_leave"});this.disposed=true;this.reset(""); }
  private reset(error:LiveState["error"]) {
    this.desired=false;this.generation++;
    if(this.joiningTimer)clearTimeout(this.joiningTimer);
    this.joiningTimer=undefined;
    this.peers.forEach(p=>{p.closed=true;p.pc.close();});this.peers.clear();
    Object.values(this.tracks).forEach(t=>t?.stop());delete this.tracks.audio;delete this.tracks.video;
    this.update({...blankLiveState(),error});
  }
  private closePeer(seat:number) {
    const p=this.peers.get(seat);if(p){p.closed=true;p.pc.close();this.peers.delete(seat);}
    const streams={...this.state.streams}, connections={...this.state.connections};delete streams[seat];delete connections[seat];this.update({streams,connections});
  }
  private valid(seat:number,p:Peer):boolean { return this.desired&&!this.disposed&&!p.closed&&this.peers.get(seat)===p; }
  private queue(seat:number,p:Peer,fn:()=>Promise<void>) {
    p.serial=p.serial.then(async()=>{if(this.valid(seat,p))await fn();}).catch(()=>{
      if(this.valid(seat,p)){this.closePeer(seat);this.update({error:"peer"});}
    });
  }
  private signal(seat:number,p:Peer,kind:"offer"|"answer"|"ice",data:RTCSessionDescriptionInit|RTCIceCandidateInit) {
    if(this.valid(seat,p)&&!this.transmit({type:"media_signal",to:seat,to_session:p.session,kind,data}))this.update({error:"transport"});
  }
  private async attachTracks(p:Peer) {
    const transceivers=p.pc.getTransceivers();
    if(transceivers.length!==2 || new Set(transceivers.map(t=>t.receiver.track.kind)).size!==2)throw new Error("Invalid media sections");
    for(const t of transceivers){
      const kind=t.receiver.track.kind as MediaKind;
      if(kind!=="audio"&&kind!=="video")throw new Error("Invalid media kind");
      t.direction="sendrecv";
      await t.sender.replaceTrack(this.tracks[kind] ?? null);
    }
  }
  private makePeer(seat:number,member:Participant) {
    if(this.peers.has(seat))return;
    try {
      const pc=new RTCPeerConnection({iceServers:ICE_SERVERS});
      const p:Peer={session:member.session,pc,pending:[],serial:Promise.resolve(),incoming:[],closed:false};this.peers.set(seat,p);
      pc.onicecandidate=e=>{if(e.candidate)this.signal(seat,p,"ice",e.candidate.toJSON());};
      pc.ondatachannel=e=>e.channel.close();
      pc.ontrack=e=>{if(!this.valid(seat,p))return;p.incoming=p.incoming.filter(t=>t.kind!==e.track.kind);p.incoming.push(e.track);this.update({streams:{...this.state.streams,[seat]:new MediaStream(p.incoming)}});};
      pc.onconnectionstatechange=()=>{if(!this.valid(seat,p))return;this.update({connections:{...this.state.connections,[seat]:pc.connectionState},...(pc.connectionState==="failed"?{error:"peer" as const}:{})});};
      if(this.seat<seat){
        pc.addTransceiver("audio",{direction:"sendrecv"});pc.addTransceiver("video",{direction:"sendrecv"});
        this.queue(seat,p,async()=>{await this.attachTracks(p);await pc.setLocalDescription(await pc.createOffer());if(pc.localDescription)this.signal(seat,p,"offer",{type:"offer",sdp:pc.localDescription.sdp});});
      }
    }catch{this.closePeer(seat);this.update({error:"peer"});}
  }
  receive(frame:LiveFrame) {
    if(!this.desired||this.disposed)return;
    if(frame.type==="media_error"){this.transmit({type:"media_leave"});this.reset("transport");return;}
    if(frame.type==="media_state"){
      const own=frame.participants[this.seat];
      if(!own){this.reset("transport");return;}
      if(this.state.joined&&this.state.roster[this.seat]?.session!==own.session){this.transmit({type:"media_leave"});this.reset("transport");return;}
      if(this.joiningTimer)clearTimeout(this.joiningTimer);this.joiningTimer=undefined;
      this.update({joining:false,joined:true,roster:frame.participants});
      for(const i of [0,1,2]){if(i===this.seat)continue;const member=frame.participants[i];const old=this.peers.get(i);if(old&&(!member||old.session!==member.session))this.closePeer(i);if(member&&!this.peers.has(i))this.makePeer(i,member);}
      return;
    }
    const p=this.peers.get(frame.from);
    if(!p||frame.to_session!==this.state.roster[this.seat]?.session||frame.from_session!==p.session)return;
    this.queue(frame.from,p,async()=>{
      const pc=p.pc;
      if(frame.kind==="ice"){
        const candidate=frame.data as RTCIceCandidateInit;
        if(pc.remoteDescription)await pc.addIceCandidate(candidate);
        else if(p.pending.length<64)p.pending.push(candidate);
        else throw new Error("Too many candidates");
      }else if(frame.kind==="offer"&&this.seat>frame.from&&pc.signalingState==="stable"&&!pc.remoteDescription){
        await pc.setRemoteDescription(frame.data as RTCSessionDescriptionInit);await this.attachTracks(p);await pc.setLocalDescription(await pc.createAnswer());if(pc.localDescription)this.signal(frame.from,p,"answer",{type:"answer",sdp:pc.localDescription.sdp});
      }else if(frame.kind==="answer"&&this.seat<frame.from&&pc.signalingState==="have-local-offer")await pc.setRemoteDescription(frame.data as RTCSessionDescriptionInit);
      if(pc.remoteDescription){const candidates=p.pending.splice(0);for(const candidate of candidates)await pc.addIceCandidate(candidate);}
    });
  }
  async toggle(kind:MediaKind) {
    if(!this.state.joined||this.state.changing||this.disposed)return;
    const generation=this.generation;this.update({changing:true,error:""});
    try {
      const previous=this.tracks[kind];
      if(previous){previous.stop();delete this.tracks[kind];}
      else {
        const acquired=await navigator.mediaDevices.getUserMedia({audio:kind==="audio",video:kind==="video"?{width:{ideal:320},height:{ideal:240},frameRate:{ideal:15,max:20}}:false});
        if(this.disposed||generation!==this.generation||!this.desired){acquired.getTracks().forEach(t=>t.stop());return;}
        const track=acquired.getTracks().find(t=>t.kind===kind);
        acquired.getTracks().filter(t=>t!==track).forEach(t=>t.stop());if(!track)throw new Error("Missing track");
        this.tracks[kind]=track;
        track.onended=()=>{if(this.tracks[kind]===track){delete this.tracks[kind];this.updateTracks();}};
      }
      this.updateTracks();
    }catch{if(!this.disposed&&generation===this.generation)this.update({error:"device"});}
    finally{if(!this.disposed&&generation===this.generation)this.update({changing:false});}
  }
  private updateTracks() {
    if(!this.desired||this.disposed)return;
    const audio=!!this.tracks.audio, video=!!this.tracks.video;
    const streams={...this.state.streams};delete streams[this.seat];
    if(audio||video)streams[this.seat]=new MediaStream(Object.values(this.tracks).filter((t):t is MediaStreamTrack=>!!t));
    this.update({audio,video,streams});
    if(!this.transmit({type:"media_presence",audio,video})){this.reset("transport");return;}
    this.peers.forEach((p,i)=>{this.queue(i,p,async()=>{if(p.pc.getTransceivers().length===2)await this.attachTracks(p);});});
  }
}
