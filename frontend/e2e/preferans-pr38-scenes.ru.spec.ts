import { expect,test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { ModuleKind,ScriptTarget,transpileModule } from "typescript";
import { illegalCardMessage, declarationMessage, auctionMessage } from "../../portfolio/preferans/frontend/src/play-status.ru";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
const source=(file:string)=>readFileSync(resolve(process.cwd(),"../portfolio/preferans/frontend/src",file),"utf8");
const base:RoomView={room_id:"a".repeat(32),version:1,status:"playing",my_seat:1,room_admin:false,occupied:[true,true,true],game_id:"g",phase:"play",declarer:0};

test("wrong move explains only the suit required by the legal move projection",()=>{
  for(const [suit,label] of [["S","пики"],["C","трефы"],["D","бубны"],["H","червы"]] as const){
    expect(illegalCardMessage({...base,legal_cards:[{suit,rank:7},{suit,rank:14}]})).toBe(`Ты чё, слепой? У тебя ${label} есть!`);
  }
  expect(illegalCardMessage({...base,legal_cards:[]})).toBe("Этой картой сейчас ходить нельзя.");
  expect(illegalCardMessage({...base,legal_cards:[{suit:"S",rank:7},{suit:"H",rank:7}]})).not.toContain("У тебя");
  expect(declarationMessage({...base,phase:"declare"},seat=>`Игрок ${seat+1}`)).toBe("Игрок 1 думает какую игру объявить");
  const bid={kind:"misere",suit:null,level:null} as const;
  const auction:RoomView={...base,phase:"auction",high_bid:bid,auction_calls:[null,{kind:"bid",bid},null]};
  expect(auctionMessage(auction)).toBeNull();
  expect(auctionMessage({...auction,my_seat:0})).not.toBeNull();
});

test("paper viewport has no artificial blank area and only drawing scrolls when enlarged",async({page})=>{
  await page.setViewportSize({width:900,height:600});
  await page.setContent(`<style>${source("preferans-notebook.module.css")} *{box-sizing:border-box}</style><div class="wrap" style="--paper-ratio:2"><div style="height:25px">Toolbar</div><span class="paperViewport" style="--paper-zoom:1"><svg class="paper" viewBox="0 0 600 300"></svg></span></div>`);
  const dimensions=()=>page.locator(".paperViewport").evaluate(el=>({w:el.clientWidth,h:el.clientHeight,sw:el.scrollWidth,sh:el.scrollHeight}));
  const base=await dimensions();
  expect(base.h).toBeGreaterThan(100);expect(base.sh-base.h).toBeLessThanOrEqual(2);
  expect(Math.abs(base.h-base.w/2)).toBeLessThanOrEqual(3);
  const outer=await page.locator(".wrap").boundingBox();
  await page.locator(".paperViewport").evaluate(el=>{(el as HTMLElement).style.setProperty("--paper-zoom","3");(el as HTMLElement).dataset.zoomed="true";});
  const big=await dimensions();expect(big.sw).toBeGreaterThan(big.w);expect(big.sh).toBeGreaterThan(big.h);
  expect(Math.abs(big.h-base.h)).toBeLessThanOrEqual(20);
  const after=await page.locator(".wrap").boundingBox();expect(Math.abs(after!.height-outer!.height)).toBeLessThanOrEqual(20);
  await page.locator(".paperViewport").evaluate(el=>el.scrollTo(80,80));
  expect(await page.locator(".paperViewport").evaluate(el=>[el.scrollLeft,el.scrollTop])).toEqual([80,80]);
});

test("gather uses old card positions and removes every temporary clone before next deal",async({page})=>{
  const compiled=transpileModule(source("table-motion.ts"),{compilerOptions:{module:ModuleKind.CommonJS,target:ScriptTarget.ES2022}}).outputText;
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  for(const scale of [.7,1,1.3]){
    await page.setContent(`<div id="table" style="width:400px;height:260px;position:relative;transform:scale(${scale});transform-origin:top left"><button style="position:absolute;left:40px;top:30px"><span data-deck-collect-target style="display:block;width:40px;height:60px"></span></button><div data-trick-train="0" style="position:absolute;left:120px;top:50px"><button style="width:25px;height:40px">A</button><button style="width:25px;height:40px">B</button></div><div data-own-hand style="position:absolute;left:140px;top:180px"><button data-card="7S" style="width:40px;height:60px">C</button></div></div>`);
    await page.addScriptTag({content:`(()=>{const exports={};\n${compiled}\nwindow.cleanup=exports.animateGather(document.getElementById('table'));})()`});
    expect(errors).toEqual([]);
    await expect(page.locator("[data-gather-clone]")).toHaveCount(3);
    const motions=await page.locator("[data-gather-clone]").evaluateAll(nodes=>nodes.map(el=>el.getAnimations()[0]?.effect instanceof KeyframeEffect?(el.getAnimations()[0].effect as KeyframeEffect).getKeyframes().length:0));
    expect(motions).toEqual([3,3,3]);
    expect(await page.locator("[data-deck-collect-target]").evaluate(el=>el.closest("button")!.inert)).toBe(true);
    await page.evaluate(()=>{(window as unknown as {cleanup:()=>void}).cleanup();});
    await expect(page.locator("[data-gather-clone]")).toHaveCount(0);
    expect(await page.locator("[data-deck-collect-target]").evaluate(el=>el.closest("button")!.inert)).toBe(false);
    await expect(page.locator("#table")).not.toHaveAttribute("data-gathering","true");
  }
});

test("tear scene separates intact paper, fragments, crumpled ball and return",async({page})=>{
  await page.emulateMedia({reducedMotion:"no-preference"});
  await page.setContent(`<style>${source("sheet-tear.module.css")}</style><div style="position:relative;width:700px;height:420px;container-type:size"><div class="scene"><div class="walker"><svg class="character" viewBox="0 0 100 160"><rect width="100" height="160"/></svg></div><div class="paper" style="height:80px;background:beige"></div><div class="piece" style="height:80px;background:beige;--dx:20px;--dy:20px;--angle:20deg"></div><svg class="ball" viewBox="0 0 60 54"><circle cx="30" cy="25" r="20"/></svg></div></div>`);
  const visible=await page.evaluate(()=>[.2,.48,.68,.91].map(fr=>{
    for(const animation of document.getAnimations()){animation.pause();animation.currentTime=fr*6800;}
    return [".paper",".piece",".ball"].map(selector=>Number(getComputedStyle(document.querySelector(selector)!).opacity));
  }));
  expect(visible).toEqual([[1,0,0],[0,1,0],[0,0,1],[0,0,0]]);
});
