import { expect,test } from "@playwright/test";
import { opponentWidowCards } from "../../portfolio/preferans/frontend/src/table-refinements";
import { GAG_MISSING_MS,GAG_FOUND_MS,GAG_RETURN_MS,GAG_FAKE_MS,GAG_TOTAL_MS,gagPhase } from "../../portfolio/preferans/frontend/src/gag-model";
import { DEAL_DURATION_MS } from "../../portfolio/preferans/frontend/src/table-motion";
import { ModuleKind, ScriptTarget, transpileModule } from "typescript";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const source=(file:string)=>readFileSync(resolve(process.cwd(),"../portfolio/preferans/frontend/src",file),"utf8");
test("normal widow review ends on the first card without changing passout rules",()=>{
  const cards=[{rank:14,suit:"S" as const},{rank:7,suit:"H" as const}];
  const view:RoomView={room_id:"a".repeat(32),version:1,game_id:"g",status:"playing",my_seat:1,room_admin:false,occupied:[true,true,true],declarer:0,phase:"play",widow:cards,played_tricks:0,trick:[]};
  expect(opponentWidowCards(view)).toEqual(cards);
  expect(opponentWidowCards({...view,trick:[{owner:0,card:cards[0]}]})).toBeNull();
  expect(opponentWidowCards({...view,played_tricks:1})).toBeNull();
  expect(opponentWidowCards({...view,my_seat:0})).toBeNull();
  expect(opponentWidowCards({...view,is_passout:true})).toBeNull();
});
test("both joke deal stages permit a full normal animation and discovery lasts 2.8s",()=>{
  expect(GAG_MISSING_MS).toBeGreaterThanOrEqual(DEAL_DURATION_MS);
  expect(GAG_FOUND_MS-GAG_MISSING_MS).toBe(2000);
  expect(GAG_RETURN_MS-GAG_FOUND_MS).toBe(2800);
  expect(GAG_TOTAL_MS-GAG_FAKE_MS).toBeGreaterThanOrEqual(DEAL_DURATION_MS);
  expect(gagPhase({seat:0,at_ms:1000},1000+GAG_FAKE_MS)).toBe("deal");
  expect(gagPhase({seat:0,at_ms:1000},1000+GAG_TOTAL_MS)).toBeNull();
});
test("expanded suits dim available levels without changing disabled opacity",async({page})=>{
  await page.setContent(`<style>${source("preferans-game.module.css")} ${source("preferans-table.module.css")}</style><main class="root tableRoot"><section class="table"><div class="bidGroups"><div><button type="button" disabled data-bid-muted="true">6</button></div><div><button type="button" aria-expanded="true">7</button><span class="bidSuits"><button type="button" data-bid-tone="suit">♠</button><button type="button" data-bid-tone="suit" data-no-trump="true">БК</button></span></div><div><button type="button" data-bid-muted="true">8</button></div></div></section></main>`);
  await expect(page.getByRole("button",{name:"6",exact:true})).toHaveCSS("opacity","0.26");
  await expect(page.getByRole("button",{name:"8",exact:true})).toHaveCSS("opacity","0.68");
  const active=await page.getByRole("button",{name:"7",exact:true}).boundingBox();
  const suit=await page.getByRole("button",{name:"♠",exact:true}).boundingBox();
  expect(active).not.toBeNull();expect(suit).not.toBeNull();
  expect(suit!.height).toBeLessThan(active!.height);
});

test("standard dealing animation supports a late scene entry at all table scales",async({page})=>{
  const compiled=transpileModule(source("table-motion.ts"),{compilerOptions:{module:ModuleKind.CommonJS,target:ScriptTarget.ES2022}}).outputText;
  const errors:string[]=[];
  page.on("pageerror",error=>errors.push(error.message));
  for(const scale of [.7,1,1.3]){
    await page.setContent(`<div id="table" style="width:500px;height:350px;position:relative;transform:scale(${scale});transform-origin:top left"><div data-play-field style="position:absolute;left:20px;top:20px;width:80px;height:50px"></div><div data-seat="0" data-position="bottom"></div><div data-seat="1" data-position="left"></div><div data-seat="2" data-position="right"></div><div data-own-hand style="position:absolute;left:200px;top:200px;display:flex;gap:12px">${["14S","13S","8H","7H"].map(id=>`<div data-hand-card style="position:relative"><button data-card="${id}" style="width:40px;height:60px">${id}</button></div>`).join("")}</div></div>`);
    await page.addScriptTag({content:`(()=>{const exports={};\n${compiled}\nwindow.cleanup=exports.animateDeal(document.getElementById('table'),2,['8H','14S','7H','13S'],500);})()`});
    const frames=await page.locator("[data-card]").evaluateAll(cards=>cards.map(card=>{const effect=card.getAnimations()[0]?.effect;return effect instanceof KeyframeEffect?{frames:effect.getKeyframes(),delay:effect.getTiming().delay}:null;}));
    expect(errors,`browser errors at scale ${scale}`).toEqual([]);
    expect(frames,`card count at scale ${scale}`).toHaveLength(4);
    expect(frames.every(item=>item?.frames.length===4),`keyframes at scale ${scale}`).toBe(true);
    expect(frames.some(item=>(item?.delay??0)<0)).toBe(true);
    expect(frames.every(item=>item?.frames[3].transform==="none")).toBe(true);
    await page.evaluate(()=>{(window as unknown as {cleanup:()=>void}).cleanup();});
    expect(await page.locator("[data-card]").evaluateAll(cards=>cards.every(card=>card.getAnimations().length===0))).toBe(true);
  }
});
