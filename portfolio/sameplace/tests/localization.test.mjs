import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { after, test } from "node:test";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const source = resolve(root, "portfolio/sameplace/frontend/src/i18n");
const requireFromHost = createRequire(resolve(root, "frontend/package.json"));
const out = mkdtempSync(join(tmpdir(), "sameplace-i18n-"));
after(() => rmSync(out, { recursive: true, force: true }));
// Compile the actual production translator, not a reimplementation of it.
const tsc = process.env.SAMEPLACE_TEST_TSC || requireFromHost.resolve("typescript/bin/tsc");
execFileSync(process.execPath, [tsc, "--strict", "--target", "ES2020", "--module", "commonjs",
  "--resolveJsonModule", "--esModuleInterop", "--skipLibCheck", "--outDir", out,
  resolve(source, "messages.ts")], { stdio: "inherit" });
const requireCompiled = createRequire(join(out, "entry.cjs"));
const { createTranslator, resolveLocale, playerCount, SUPPORTED_LOCALES } = requireCompiled("./messages.js");
const raw = readFileSync(resolve(source, "messages.ru.json"), "utf8");
const ru = JSON.parse(raw);
const placeholders = (value) => [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g)].map((m) => m[1]).sort();

test("Russian is the only enabled locale and fallback is deterministic", () => {
  assert.deepEqual(SUPPORTED_LOCALES, ["ru"]);
  for (const language of ["ru-RU", "RU", "en", "uk-UA", undefined, ""]) assert.equal(resolveLocale(language), "ru");
  assert.equal(createTranslator("en")("foundation.motto"), ru["foundation.motto"]);
});
test("translation keys are unique, complete and nonempty", () => {
  const keys = [...raw.matchAll(/^\s*"([^"\r\n]+)"\s*:/gm)].map((m) => m[1]);
  assert.equal(new Set(keys).size, keys.length);
  assert.deepEqual(keys.sort(), Object.keys(ru).sort());
  for (const key of ["foundation.stage", "foundation.motto", "foundation.description", "foundation.notice", "fallback.missing", "players.one", "players.few", "players.many", "players.other"]) {
    assert.ok(typeof ru[key] === "string" && ru[key].trim());
  }
  for (const key of ["players.one", "players.few", "players.many", "players.other"]) assert.deepEqual(placeholders(ru[key]), ["count"]);
});
test("Russian plural rules use all relevant categories", () => {
  for (const [n, key] of [[0,"many"],[1,"one"],[2,"few"],[5,"many"],[11,"many"],[21,"one"],[22,"few"],[25,"many"]]) {
    assert.equal(playerCount(n), ru[`players.${key}`].replace("{count}", String(n)));
  }
  assert.throws(() => playerCount(-1), RangeError);
});
test("missing keys and parameters fail safely without exposing machine errors", () => {
  assert.equal(createTranslator("ru")("unknown.key"), ru["fallback.missing"]);
  assert.equal(createTranslator("ru")("players.one"), ru["fallback.missing"]);
  assert.throws(() => createTranslator("ru", { strict: true })("unknown.key"));
  assert.throws(() => createTranslator("ru", { strict: true })("players.one"));
});
test("pseudo translation stretches labels without changing identifiers or the default dictionary", () => {
  const pseudo = Object.fromEntries(Object.entries(ru).map(([k, v]) => [k, `[${v} ${v.replace(/\{[^}]+\}/g, "")}]`]));
  for (const k of Object.keys(ru)) assert.deepEqual(placeholders(pseudo[k]), placeholders(ru[k]));
  const t = createTranslator("ru", { strict: true, dictionary: pseudo });
  assert.ok(t("foundation.motto").length > ru["foundation.motto"].length);
  assert.ok(t("players.one", { count: 1 }).includes("1"));
  assert.equal(createTranslator("ru")("foundation.motto"), ru["foundation.motto"]);
});


// Compile the actual allowlist separately to preserve the translator output path.
execFileSync(process.execPath, [tsc, "--strict", "--target", "ES2020", "--module", "commonjs", "--outDir", join(out, "transport"), resolve(source, "../room-transport.ts")], { stdio: "inherit" });
const { roomOperation, validInviteToken } = requireCompiled("./transport/room-transport.js");
test("BFF allows only exact SamePlace room operations and methods", () => {
  assert.equal(roomOperation("GET", ["rooms", "friday"]), "rooms/friday");
  assert.equal(roomOperation("POST", ["rooms", "friday", "invite"]), "rooms/friday/invite");
  assert.equal(roomOperation("POST", ["rooms", "friday", "design"]), "rooms/friday/design");
  for (const parts of [["rooms", "../secret"], ["rooms", "abc", "arbitrary"], ["rooms", "abc", "invite", "extra"], ["admin", "unknown"], ["preferans", "rooms"], ["rooms", "a%2Fb"]]) assert.equal(roomOperation("POST", parts), null);
  assert.equal(roomOperation("GET", ["rooms", "friday", "archive"]), null);
  assert.equal(roomOperation("DELETE", ["rooms", "friday"]), null);
  assert.equal(validInviteToken("a".repeat(32) + "." + "B".repeat(43)), true);
  assert.equal(validInviteToken("../token"), false);
});


test("SP03 allows only registered social, chat, location and ticket operations", () => {
  for (const [method, parts] of [["GET", ["social","me"]], ["POST",["social","profile"]], ["POST",["social","friend"]], ["POST",["social","read_notice"]], ["GET",["rooms","friday","chat"]], ["POST",["rooms","friday","chat","page"]], ["POST",["rooms","friday","chat","send"]], ["POST",["rooms","friday","chat","hide"]], ["POST",["rooms","friday","chat","cleanup"]], ["POST",["rooms","friday","location","propose"]], ["POST",["rooms","friday","location","answer"]], ["POST",["rooms","friday","location","cancel"]], ["POST",["rooms","friday","location","move"]], ["GET",["rooms","friday","recipients"]], ["POST",["rooms","friday","ping"]], ["POST",["rooms","friday","ticket"]], ["POST",["rooms","friday","favourite"]]]) {
    assert.equal(roomOperation(method,parts),parts.join("/"));
  }
  for (const [method, parts] of [["GET",["rooms","friday","ticket"]],["POST",["social","directory"]],["POST",["rooms","friday","chat","arbitrary"]],["POST",["rooms","friday","location","answer","extra"]],["GET",["realtime"]],["POST",["rooms","../other","ping"]]]) assert.equal(roomOperation(method,parts),null);
});
execFileSync(process.execPath,[tsc,"--strict","--target","ES2020","--module","commonjs","--outDir",join(out,"layout"),resolve(source,"../social/layout.ts")],{stdio:"inherit"});
const {positions}=requireCompiled("./layout/layout.js");
test("participant layouts have deterministic non-overlapping places for 0-10 people",()=>{
  assert.deepEqual(positions(2),["5 / 1","1 / 5"]);
  assert.deepEqual(positions(3),["5 / 3","1 / 1","1 / 5"]);
  assert.deepEqual(positions(4),["5 / 3","3 / 1","1 / 3","3 / 5"]);
  for(let n=0;n<=10;n++){assert.equal(positions(n).length,n);assert.equal(new Set(positions(n)).size,n);}
  assert.throws(()=>positions(11),RangeError);
});

// SP04: production audio timing and exact new BFF operations.
execFileSync(process.execPath,[tsc,"--strict","--target","ES2020","--module","commonjs","--outDir",join(out,"decor"),resolve(source,"../decor/audio.ts")],{stdio:"inherit"});
const {targetPosition,demoWave}=requireCompiled("./decor/audio.js");
test("SP04 permits only exact decor read and write operations",()=>{
  assert.equal(roomOperation("GET",["rooms","friday","decor"]),"rooms/friday/decor");
  for(const action of ["publish","save_template","delete_template","music"]){
    assert.equal(roomOperation("POST",["rooms","friday","decor",action]),`rooms/friday/decor/${action}`);
    assert.equal(roomOperation("GET",["rooms","friday","decor",action]),null);
  }
  assert.equal(roomOperation("POST",["rooms","friday","decor","arbitrary"]),null);
  assert.equal(roomOperation("POST",["rooms","../secret","decor","music"]),null);
});
test("recorded audio uses epoch and wraparound; radio has no seek target",()=>{
  const state={position_ms:7000,started_at_ms:10000,playback:"playing"};
  assert.equal(targetPosition(state,{duration_ms:8000},12500),1.5);
  assert.equal(targetPosition({...state,playback:"paused"},{duration_ms:8000},12500),7);
  assert.equal(targetPosition(state,{duration_ms:null},12500),0);
});
test("original demo WAVs have correct headers, duration and distinct bytes",async()=>{
  const a=Buffer.from(await demoWave("test_disco").arrayBuffer());
  const b=Buffer.from(await demoWave("test_retro").arrayBuffer());
  assert.equal(a.toString("ascii",0,4),"RIFF");assert.equal(a.toString("ascii",8,12),"WAVE");
  assert.equal(a.readUInt32LE(24),16000);assert.equal(a.readUInt32LE(40),256000);
  assert.equal(a.length,256044);assert.notDeepEqual(a,b);assert.throws(()=>demoWave("untrusted"));
});
test("scene, assets, device and audio source labels exist",()=>{
  for(const id of ["apartment","garage","beach","kindergarten_boat","card_club","table_round","table_square","table_felt","mat_blue","mat_striped","boat_deck","boat_bench","chair_wood","chair_metal","lamp","plant","bag","speaker_s50","cushion","vesna_212s4","vega_122s_two_tier","mayak_233","test_disco","test_retro","melodia_disco","radio_roks","retro_radio"]){assert.ok(ru[`decor.${id}`],id);}
});
// SP05: compile the production transport, preferences and RTC controller.
execFileSync(process.execPath,[tsc,"--strict","--target","ES2020","--module","commonjs","--lib","ES2020,DOM,DOM.Iterable","--skipLibCheck","--outDir",join(out,"media"),resolve(source,"../media/types.ts"),resolve(source,"../media/preferences.ts"),resolve(source,"../media/mesh.ts")],{stdio:"inherit"});
const {parseMedia}=requireCompiled("./media/types.js");
const {DEFAULT_AUDIO,normalizeAudio,musicGain,busGain}=requireCompiled("./media/preferences.js");
const {MeshProvider}=requireCompiled("./media/mesh.js");
const mid="d".repeat(32),pid="b".repeat(32),pair="c".repeat(32);
const mediaState=(overrides={})=>({type:"media.state",meeting_id:mid,mode:"room",joined:true,occupied:false,muted:false,peers:[{id:pid,pair,offerer:true,muted:false,microphone:false,camera:false}],ice_servers:[],...overrides});
test("SP05 media parser rejects foreign meeting, bad peer, TURN and oversized SDP",()=>{
  assert.ok(parseMedia(mediaState(),mid));assert.equal(parseMedia(mediaState(),"other"),null);
  assert.equal(parseMedia(mediaState({ice_servers:[{urls:"turn:example.invalid"}]}),mid),null);
  assert.equal(parseMedia(mediaState({peers:[{id:"bad",pair}]}),mid),null);
  assert.equal(parseMedia({type:"media.signal",from:pid,pair,signal:{kind:"offer",sdp:"x".repeat(24001)}},mid),null);
  assert.ok(parseMedia({type:"media.signal",from:pid,pair,signal:{kind:"ice",candidate:"candidate:fixture",sdpMid:"0",sdpMLineIndex:0}},mid));
});
test("SP05 audio preferences clamp values, duck only music and mute every bus",()=>{
  const p=normalizeAudio({voices:200,music:40,ambient:-5,game:50,duck:true,masterMute:false});
  assert.equal(p.voices,100);assert.equal(p.ambient,0);assert.equal(musicGain(p,true),0.1);assert.equal(musicGain(p,false),0.4);
  assert.equal(busGain(p,"voices",true),1);assert.equal(busGain(p,"game",true),0.5);
  for(const bus of ["voices","music","ambient","game"])assert.equal(busGain({...p,masterMute:true},bus,true),0);
  assert.equal(normalizeAudio({microphone:"x".repeat(513)}).microphone,"");assert.deepEqual(normalizeAudio(null),DEFAULT_AUDIO);
});
test("SP05 localized media controls have distinct readable labels",()=>{
  for(const key of ["media.join","media.leave","media.mic_on","media.cam_on","media.room","media.location","media.muted","media.duck","media.diagnostics"])assert.ok(ru[key],key);
  assert.notEqual(ru["media.mic_on"],ru["media.mic_off"]);
});
test("SP05 controller uses one offer, explicit capture, moderator mute and teardown",async()=>{
  const saved=new Map(["navigator","MediaStream","RTCPeerConnection"].map(key=>[key,Object.getOwnPropertyDescriptor(globalThis,key)]));
  let captures=0,view,release;const peers=[];const sent=[];
  class Track {constructor(kind){this.kind=kind;this.readyState="live";}stop(){this.readyState="ended";}}
  class Stream {constructor(tracks=[]){this.tracks=tracks;}getTracks(){return this.tracks;}addTrack(track){this.tracks.push(track);}}
  class FakePeer {
    constructor(){this.transceivers=[];this.remoteDescription=null;this.connectionState="new";this.closed=false;peers.push(this);}
    addTransceiver(kind){this.transceivers.push({direction:"sendrecv",receiver:{track:{kind}},sender:{track:null,async replaceTrack(track){this.track=track;},getParameters(){return {encodings:[{}]};},async setParameters(){}}});}
    getTransceivers(){return this.transceivers;}
    async createOffer(){return {type:"offer",sdp:"v=0"};}async setLocalDescription(){}async setRemoteDescription(value){this.remoteDescription=value;}
    async addIceCandidate(){}async getStats(){return new Map();}close(){this.closed=true;}
  }
  Object.defineProperty(globalThis,"navigator",{configurable:true,value:{mediaDevices:{getUserMedia:async constraints=>{captures++;const track=new Track(constraints.audio?"audio":"video");if(release===null)return new Promise(resolve=>{release=()=>resolve(new Stream([track]));});return new Stream([track]);}}}});
  Object.defineProperty(globalThis,"MediaStream",{configurable:true,value:Stream});Object.defineProperty(globalThis,"RTCPeerConnection",{configurable:true,value:FakePeer});
  const provider=new MeshProvider(value=>{view=value;});
  try{
    provider.transport(frame=>{sent.push(frame);return true;});provider.receive(mediaState());
    await new Promise(resolve=>setImmediate(resolve));assert.equal(captures,0);assert.equal(sent.filter(f=>f.signal?.kind==="offer").length,1);
    await provider.toggle("audio");const track=view.local.getTracks()[0];assert.equal(captures,1);assert.equal(view.microphone,true);
    provider.receive(mediaState({muted:true}));assert.equal(track.readyState,"ended");assert.equal(view.microphone,false);
    provider.receive(mediaState());assert.equal(view.microphone,false);assert.equal(captures,1);
    release=null;const pending=provider.toggle("video");assert.equal(captures,2);provider.transport(null);release();await pending;
    assert.equal(view.camera,false);assert.equal(view.local,null);assert.equal(peers[0].closed,true);assert.deepEqual(view.remote,{});
  }finally{provider.dispose();for(const [key,descriptor] of saved){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key];}}
});
