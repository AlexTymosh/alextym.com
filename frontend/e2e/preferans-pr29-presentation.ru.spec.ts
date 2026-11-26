import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import ts from "typescript";
import { passoutWidowFrame, visibleWidow, replayWidow } from "../../portfolio/preferans/frontend/src/interaction-model";
import { claimVoteLabels } from "../../portfolio/preferans/frontend/src/claim-copy.ru";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

const first={rank:7,suit:"S"} as const,second={rank:8,suit:"H"} as const;
const base:RoomView={room_id:"a".repeat(32),version:3,status:"playing",occupied:[true,true,true],my_seat:0,room_admin:false,game_id:"deal",phase:"play",is_passout:true,played_tricks:1,widow:[first,second]};
const root=resolve(process.cwd(),"../portfolio/preferans/frontend/src");
const read=(name:string)=>readFileSync(resolve(root,name),"utf8");

test("passout widow stays on the preceding frame until collection ends",()=>{
  const snapshot=JSON.stringify(base);
  const held=passoutWidowFrame(base,true);
  expect(held.held).toBe(true);
  expect(visibleWidow(held.view)).toEqual({count:2,cards:[first]});
  expect(replayWidow(held.view)).toEqual([first]);
  expect(visibleWidow(passoutWidowFrame(base,false).view)).toEqual({count:1,cards:[second]});
  const next={...base,played_tricks:2};
  expect(visibleWidow(passoutWidowFrame(next,true).view)).toEqual({count:1,cards:[second]});
  expect(visibleWidow(passoutWidowFrame(next,false).view)).toEqual({count:0,cards:[]});
  expect(passoutWidowFrame({...base,is_passout:false},true).held).toBe(false);
  expect(JSON.stringify(base)).toBe(snapshot);
});

test("claim labels distinguish passouts, both miseres and other claimants",()=>{
  expect(claimVoteLabels(base,0)).toEqual({approve:"так ему и надо!",reject:"Я против! (отэто я гоню...)"});
  for(const kind of ["misere","misere_no_widow"] as const){
    const view:RoomView={...base,is_passout:false,declarer:1,contract:{kind,level:null,suit:null}};
    expect(claimVoteLabels(view,1)).toEqual({approve:"Шикарно всунули!",reject:"Я туплю - я против!"});
    expect(claimVoteLabels(view,0)).toEqual({approve:"Согласен",reject:"Хер там!"});
  }
});

test("collection callback waits for the actual card flight and cancels stale completions",async({page})=>{
  await page.setContent(`<div id="table"><div data-play-field><div data-trick-seat="0"><span style="display:block;width:30px;height:45px">A</span></div><div data-trick-seat="1"><span style="display:block;width:30px;height:45px">B</span></div><div data-trick-seat="2"><span style="display:block;width:30px;height:45px">C</span></div></div><div data-trick-train="1"><button data-latest="true">Trick</button></div></div>`);
  const output=ts.transpileModule(read("table-motion.ts"),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  await page.addScriptTag({content:`(()=>{const exports={};${output}\nwindow.testMotion=exports;})()`});
  await page.evaluate(()=>{
    const motion=(window as unknown as {testMotion:{animateCollection:(table:HTMLElement,winner:number,done:()=>void)=>()=>void}}).testMotion;
    const table=document.getElementById("table")!;
    table.dataset.complete="no";
    const cancel=motion.animateCollection(table,1,()=>{table.dataset.complete="stale";});
    cancel();
    motion.animateCollection(table,1,()=>{table.dataset.complete="yes";});
  });
  await expect(page.locator("#table")).toHaveAttribute("data-complete","no");
  await expect(page.locator("body > [inert]")).toHaveCount(3);
  await expect(page.locator("#table")).toHaveAttribute("data-complete","yes",{timeout:5000});
  await expect(page.locator("body > [inert]")).toHaveCount(0);
});

test("widow label remains inside the card and cannot capture pointer events",async({page})=>{
  await page.setContent(`<style>${read("preferans-game.module.css")}\n*{box-sizing:border-box}</style><main class="tableRoot"><div class="cardWithSort" data-from-widow="true" style="--card-w:100px"><button class="playingCard"><span class="widowLabel">прикуп</span></button></div></main>`);
  const label=page.locator(".widowLabel"),card=page.locator(".playingCard");
  await expect(label).toHaveCSS("pointer-events","none");
  await expect(label).toHaveCSS("writing-mode","vertical-rl");
  await expect(card).not.toHaveCSS("outline-style","dashed");
  const a=(await label.boundingBox())!,b=(await card.boundingBox())!;
  expect(a.x).toBeGreaterThanOrEqual(b.x);
  expect(a.y).toBeGreaterThanOrEqual(b.y);
  expect(a.x+a.width).toBeLessThanOrEqual(b.x+b.width);
  expect(a.y+a.height).toBeLessThanOrEqual(b.y+b.height);
});

test("photographic materials are local and selected with the existing cycle control",()=>{
  const css=read("preferans-table.module.css");
  for(const key of ["pine","cloth","plastic","plain"]){
    const data=readFileSync(resolve(root,`materials/${key}.jpg`));
    expect(data.subarray(0,2).toString("hex")).toBe("ffd8");
    expect(data.length).toBeGreaterThan(1000);
    expect(css).toContain(`url('./materials/${key}.jpg')`);
  }
  expect(read("PreferansGame.ru.tsx")).toContain('<CycleSetting<typeof surface> label="Поверхность круглого стола"');
});
