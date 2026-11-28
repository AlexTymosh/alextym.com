#!/usr/bin/env node
// Optional local Chromium smoke using actual compiled MeshProvider and virtual
// devices; no Firebase, external requests, website account or paid provider.
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {mkdtempSync,readFileSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join,resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {createRequire} from "node:module";
const root=fileURLToPath(new URL("../../../",import.meta.url));
const requireHost=createRequire(resolve(root,"frontend/package.json"));
const {chromium}=requireHost("@playwright/test");
const temp=mkdtempSync(join(tmpdir(),"sameplace-media-"));
let browser;
try{
  const media=resolve(root,"portfolio/sameplace/frontend/src/media");
  execFileSync(process.execPath,[requireHost.resolve("typescript/bin/tsc"),"--strict","--target","ES2020","--module","commonjs","--lib","ES2020,DOM,DOM.Iterable","--skipLibCheck","--outDir",temp,resolve(media,"types.ts"),resolve(media,"mesh.ts")],{stdio:"inherit"});
  const modules=["types","mesh"].map(name=>`register(${JSON.stringify("./"+name)},(exports,require)=>{${readFileSync(join(temp,name+".js"),"utf8")}\n});`).join("\n");
  const bundle=`(()=>{const mods={},cache={};const register=(name,fn)=>mods[name]=fn;const require=(name)=>{if(!cache[name]){const exports={};cache[name]=exports;mods[name](exports,require);}return cache[name];};${modules}\nwindow.MeshProvider=require("./mesh").MeshProvider;})();`;
  browser=await chromium.launch({headless:true,args:["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream"]});
  const context=await browser.newContext({permissions:["camera","microphone"]});
  const page=await context.newPage();
  await page.route("**/*",route=>route.request().url()==="http://localhost:8765/"?route.fulfill({status:200,contentType:"text/html",body:"<html><body></body></html>"}):route.abort());
  await page.goto("http://localhost:8765/");
  await page.addScriptTag({content:bundle});
  await page.evaluate(()=>{
    const aId="a".repeat(32),bId="b".repeat(32),pair="c".repeat(32),meeting="d".repeat(32);
    const views={};const a=new window.MeshProvider(v=>views.a=v),b=new window.MeshProvider(v=>views.b=v);
    window.testMedia={a,b,views};
    const state=(id,offerer)=>({type:"media.state",meeting_id:meeting,mode:"room",joined:true,occupied:false,muted:false,peers:[{id,pair,offerer,muted:false,microphone:false,camera:false}],ice_servers:[]});
    a.transport(frame=>{if(frame.type==="media.signal")queueMicrotask(()=>b.receive({type:"media.signal",from:aId,pair,signal:frame.signal}));return true;});
    b.transport(frame=>{if(frame.type==="media.signal")queueMicrotask(()=>a.receive({type:"media.signal",from:bId,pair,signal:frame.signal}));return true;});
    a.receive(state(bId,true));b.receive(state(aId,false));
  });
  await page.waitForFunction(()=>window.testMedia.views.a.connections["b".repeat(32)]==="connected"&&window.testMedia.views.b.connections["a".repeat(32)]==="connected",{},{timeout:15000});
  assert.equal(await page.evaluate(()=>window.testMedia.views.a.local),null);
  await page.evaluate(async()=>{await window.testMedia.a.toggle("audio");await window.testMedia.a.toggle("video");});
  await page.waitForFunction(()=>window.testMedia.views.a.camera&&window.testMedia.views.a.microphone&&window.testMedia.views.b.remote["a".repeat(32)]?.getVideoTracks().some(t=>!t.muted),{},{timeout:15000});
  await page.evaluate(()=>{const video=document.createElement("video");video.muted=true;video.autoplay=true;video.srcObject=window.testMedia.views.b.remote["a".repeat(32)];document.body.append(video);});
  await page.waitForFunction(()=>document.querySelector("video")?.videoWidth>0,{},{timeout:10000});
  const result=await page.evaluate(()=>{const {a,b,views}=window.testMedia;const tracks=views.a.local.getTracks();a.transport(null);b.transport(null);return {tracks:tracks.map(t=>t.readyState),remote:Object.keys(views.b.remote),camera:views.a.camera,mic:views.a.microphone};});
  assert.deepEqual(result,{tracks:["ended","ended"],remote:[],camera:false,mic:false});
  console.log("SamePlace browser media smoke: PASS (virtual devices, local mesh; not real network acceptance)");
}finally{if(browser)await browser.close();rmSync(temp,{recursive:true,force:true});}
