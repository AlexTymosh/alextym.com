import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { ModuleKind, ScriptTarget, transpileModule } from "typescript";
import { mergeHintSnapshot, sharedHint } from "../../portfolio/preferans/frontend/src/defense-hints";
import { validClaim } from "../../portfolio/preferans/frontend/src/claim-model";
import type { Card, RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

const source=(file:string)=>readFileSync(resolve(process.cwd(),"../portfolio/preferans/frontend/src",file),"utf8");
const card:Card={suit:"H",rank:14};
const base:RoomView={room_id:"a".repeat(32),version:10,game_id:"g",status:"playing",phase:"play",my_seat:1,room_admin:false,occupied:[true,true,true],declarer:0,contract:{kind:"regular",level:7,suit:"S"},mode:"open",defense:[null,"vist","pass"],hand:[],open_hands:[{seat:2,cards:[card]}],defense_hints:[]};

test("same-version HTTP views preserve shared cue state, explicit removal and new deal win",()=>{
  const marked={...base,defense_hints:[{owner:2,card}]};
  const http={...base,defense_hints:undefined};
  expect(sharedHint(marked,2,card)).toBe(true);
  expect(sharedHint({...marked,mode:"closed"},2,card)).toBe(false);
  expect(mergeHintSnapshot(marked,http,true).defense_hints).toEqual(marked.defense_hints);
  expect(mergeHintSnapshot(marked,base,true).defense_hints).toEqual([]);
  expect(mergeHintSnapshot(marked,{...http,version:11},true).defense_hints).toBeUndefined();
  expect(mergeHintSnapshot(marked,http,false).defense_hints).toBeUndefined();
});

test("by-own pending claim can reveal only valid cards and terminal projection is empty",()=>{
  const claim={seat:0,status:"pending",voters:[1],approved:[],rejected_by:null,awarded:0,cards:[card],defender_target:3,awards:[0,0,0]};
  expect(validClaim(claim,base as unknown as Record<string,unknown>)).toBe(true);
  expect(validClaim({...claim,cards:[{suit:"H",rank:2}]},base as unknown as Record<string,unknown>)).toBe(false);
  expect(validClaim({...claim,status:"rejected",rejected_by:1},base as unknown as Record<string,unknown>)).toBe(false);
  expect(validClaim({...claim,status:"rejected",rejected_by:1,cards:[]},base as unknown as Record<string,unknown>)).toBe(true);
});

test("central hand stays inside the table at all element scales on a short screen",async({page})=>{
  await page.setViewportSize({width:1272,height:624});
  await page.setContent(`<meta name="viewport" content="width=device-width,initial-scale=1"><style>${source("preferans-game.module.css")} ${source("preferans-table.module.css")} *{box-sizing:border-box}body{margin:0}</style><main class="root tableRoot"><div class="tableScene" style="--table-zoom:1;width:1240px"><section class="table" data-playing="true" data-furniture="true" style="--available-table-height:450px"><div class="tableTop"><div class="seat"><div class="avatar"></div></div><div class="center"><div class="trickField"></div></div><div class="seat"><div class="avatar"></div></div></div><div class="bottomArea" style="--hand-count:12;--hand-breaks:3"><div class="seat bottom"><div class="avatar"></div></div><div class="handColumn"><div class="trickStackWrap"><button class="trickStack">A</button></div><div class="claimButton"><button>Все мои</button><button>По своим</button></div><div class="ownHand" data-own-hand="true"><div class="handsPanel" data-discard-inline="true"><div class="declareRow"><div class="discardReview"><div class="discardSlots"><span class="discardSlot"></span><span class="discardSlot"></span><button>◉</button></div></div></div><div class="handRow">${Array.from({length:12},(_,i)=>`<div class="cardWithSort" data-suit-break="${i%3===0&&i>0}"><button class="playingCard" data-card="${i}" ${i===2?'data-defense-raised="true"':""} style="background:white"></button></div>`).join("")}</div></div></div></div><div class="bottomFurniture">Radio</div></div></section></div></main>`);
  const table=page.locator(".table"), field=page.locator(".trickField");
  const tableBox=(await table.boundingBox())!, fieldBox=(await field.boundingBox())!;
  for(const zoom of [.7,1,1.3]){
    await page.locator(".tableScene").evaluate((el,value)=>(el as HTMLElement).style.setProperty("--table-zoom",String(value)),zoom);
    const boxes=await page.locator("[data-card]").evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};}));
    expect(boxes.every(r=>r.w>8&&r.y>=tableBox.y&&r.y+r.h<=tableBox.y+tableBox.height-3),`scale ${zoom}`).toBe(true);
    expect((await field.boundingBox())!.width).toBeCloseTo(fieldBox.width,0);
    expect((await table.boundingBox())!.height).toBeCloseTo(tableBox.height,0);
  }
});

test("cue moves toward center for side hands and upward for own hand",async({page})=>{
  await page.setContent(`<meta name="viewport" content="width=device-width,initial-scale=1"><style>${source("preferans-game.module.css")} ${source("preferans-table.module.css")}</style><main class="root tableRoot"><section class="table"><div data-position="left" class="openHand"><button id="side" class="playingCard" data-defense-raised="true" style="width:40px;height:60px"></button></div><div data-position="bottom"><button id="own" class="playingCard" data-defense-raised="true" style="width:40px;height:60px"></button></div></section></main>`);
  const shift=(id:string)=>page.locator(id).evaluate(el=>new DOMMatrix(getComputedStyle(el).transform).m42);
  expect(await shift("#side")).toBeCloseTo(10.8,1);
  expect(await shift("#own")).toBeCloseTo(-10.8,1);
});

test("decorative deck counts down 32 and 30 cards and disappears after last packet",async({page})=>{
  const compiled=transpileModule(source("table-motion.ts"),{compilerOptions:{module:ModuleKind.CommonJS,target:ScriptTarget.ES2022}}).outputText;
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  for(const fake of [false,true]){
    for(const elapsed of [0,1500,2100]){
      await page.setContent(`<div id="table" style="position:relative;width:700px;height:500px"><div data-play-field style="position:absolute;left:300px;top:160px;width:100px;height:100px"></div><div data-seat="0" data-position="bottom"></div>${[1,2].map(seat=>`<div data-seat="${seat}" data-position="left">${Array.from({length:10},()=>'<span data-card-back style="display:inline-block;width:35px;height:50px"></span>').join("")}</div>`).join("")}<div data-own-hand>${Array.from({length:10},(_,i)=>`<div data-hand-card style="display:inline-block"><button data-card="${i}" style="width:40px;height:60px">${i}</button></div>`).join("")}</div><div data-widow-zone><img style="width:40px;height:60px"><img style="width:40px;height:60px"></div></div>`);
      await page.addScriptTag({content:`(()=>{const exports={};${compiled}\nwindow.cleanup=exports.animateDeal(document.getElementById('table'),2,[],${elapsed},undefined,${fake});window.remaining=document.querySelector("[data-deal-stack]")?.dataset.dealRemaining??null;})()`});
      const deck=page.locator("[data-deal-stack]");
      if(elapsed===0)expect(await page.evaluate(()=>(window as unknown as {remaining:string|null}).remaining)).toBe(fake?"28":"30");
      if(elapsed===1500)await expect(deck).toHaveCount(1);
      if(elapsed===2100)await expect(deck).toHaveCount(0);
      if(fake)expect(await page.locator("[data-widow-zone] img").evaluateAll(nodes=>nodes.every(n=>n.getAnimations().length===0))).toBe(true);
      await page.evaluate(()=>{(window as unknown as {cleanup:()=>void}).cleanup();});
      await expect(deck).toHaveCount(0);
    }
  }
  expect(errors).toEqual([]);
});
