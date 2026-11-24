import { expect, test } from "@playwright/test";
import { emptyRoster, isMediaEnvelope, parseLiveFrame } from "../../portfolio/preferans/frontend/src/live-media-model";
import { parseRealtimeFrame } from "../../portfolio/preferans/frontend/src/realtime-client";
import { LiveMediaSession, type LiveState } from "../../portfolio/preferans/frontend/src/live-media-session";
import type { LiveCommand } from "../../portfolio/preferans/frontend/src/live-media-model";

const session = (s:string) => s.repeat(32);
const envelope = {protocol:1, server_now_ms:1000};
const participant = {session:session("a"),audio:false,video:false};
const signal = {...envelope,type:"media_signal",from:1,from_session:session("b"),to_session:session("a"),kind:"offer",data:{type:"offer",sdp:"v=0\r\n"}};

test("live channel only accepts scoped, bounded media messages",()=>{
  expect(parseLiveFrame(JSON.stringify(signal),0)).toMatchObject({type:"media_signal",from:1});
  expect(parseLiveFrame(JSON.stringify(signal),1)).toBeNull();
  expect(parseLiveFrame(JSON.stringify({...signal,to_session:"bad"}),0)).toBeNull();
  expect(parseLiveFrame(JSON.stringify({...signal,data:{type:"offer",sdp:"x".repeat(12001)}}),0)).toBeNull();
  expect(parseLiveFrame(JSON.stringify({...signal,kind:"ice",data:{candidate:"x",sdpMLineIndex:true}}),0)).toBeNull();
  expect(parseLiveFrame(JSON.stringify({...signal,protocol:2}),0)).toBeNull();
  expect(parseLiveFrame(JSON.stringify({...envelope,type:"media_state",participants:[participant,null,null]}),0)).toMatchObject({participants:[participant,null,null]});
  expect(parseLiveFrame(JSON.stringify({...envelope,type:"media_state",participants:[participant]}),0)).toBeNull();
  expect(isMediaEnvelope(JSON.stringify(signal))).toBe(true);
  expect(isMediaEnvelope("{" )).toBe(false);
});

test("media negotiation is optional for old game clients",()=>{
  const room=session("a");
  const base={...envelope,type:"snapshot",presence:["online","online","online"],view:{room_id:room,version:7,status:"playing",occupied:[true,true,true],my_seat:0,room_admin:false}};
  expect(parseRealtimeFrame(JSON.stringify(base),room,0)?.type).toBe("snapshot");
  expect(parseRealtimeFrame(JSON.stringify({...base,live_media:true}),room,0)?.type).toBe("snapshot");
  expect(parseRealtimeFrame(JSON.stringify(signal),room,0)).toBeNull();
});

test("explicit join is receive-only and dispose releases the session",()=>{
  const sent:LiveCommand[]=[];
  const states:LiveState[]=[];
  const engine=new LiveMediaSession(0,message=>{sent.push(message);return true;},state=>states.push(state));
  try {
    engine.join();
    expect(sent).toEqual([{type:"media_join"}]);
    engine.receive({type:"media_state",participants:[participant,null,null]});
    expect(states.at(-1)).toMatchObject({joined:true,audio:false,video:false});
    engine.leave();
    expect(states.at(-1)).toMatchObject({joined:false,audio:false,video:false,roster:emptyRoster()});
    expect(sent.at(-1)).toEqual({type:"media_leave"});
    engine.receive({type:"media_state",participants:[participant,null,null]});
    expect(states.at(-1)?.joined).toBe(false);
  } finally {engine.dispose();}
});
