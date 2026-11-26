import { expect, test } from "@playwright/test";
import { notebookAt } from "../../portfolio/preferans/frontend/src/notebook-history";
import { safeProfiles } from "../../portfolio/preferans/frontend/src/table-model";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

test("historical notebook projection never changes live balances",()=>{
  const sheet:NonNullable<RoomView["score_sheet"]>={exact:true,hill:[[],[],[]],pool:[[2,4],[],[]],vists:[[[],[],[]],[[],[],[]],[[8],[],[]]],steps:[
    {kind:"deal",declarer:0,entries:[{field:"pool",seat:0,against:null,index:0,delta:2,reason:"regular"},{field:"vist",seat:2,against:0,index:0,delta:8,reason:"half"}]},
    {kind:"deal",declarer:0,entries:[{field:"pool",seat:0,against:null,index:1,delta:2,reason:"regular"}]},
  ]};
  const before=JSON.stringify(sheet);
  expect(notebookAt(sheet,0).pool).toEqual([[],[],[]]);
  const step=notebookAt(sheet,1);
  expect(step.pool[0]).toEqual([2]);expect(step.vists[2][0]).toEqual([8]);
  expect(step.marks?.filter(m=>m.latest)).toHaveLength(2);
  expect(JSON.stringify(sheet)).toBe(before);
});
test("room profile accepts only separately projected email fallback",()=>{
  expect(safeProfiles({profiles:[{name:"Name",email:"test@example.invalid"},{name:null,email:"test@example.invalid"},{name:"untrusted@example.invalid"}]})).toEqual([{name:"Name",avatar:null},{name:"test@example.invalid",avatar:null},{name:null,avatar:null}]);
});
const root=resolve(process.cwd(),"../portfolio/preferans/frontend/src");
const read=(name:string)=>readFileSync(resolve(root,name),"utf8");
for(const [width,height] of [[1440,900],[800,450],[568,320]]){
  test(`avatar remains fixed when cards disappear at ${width}x${height}`,async({page})=>{
    await page.setViewportSize({width,height});
    const cards=Array.from({length:12},(_,i)=>`<div class="cardWithSort" ${[3,6,9].includes(i)?'data-suit-break="true"':''}><button class="playingCard"></button></div>`).join("");
    await page.setContent(`<meta name="viewport" content="width=device-width,initial-scale=1"><style>${read("preferans-game.module.css")}\n${read("preferans-table.module.css")}\n${read("preferans-shared.module.css").replace(/\.(left|right|bottom|panel|scoreClose|viewerTitle)(?![\w-])/g,".shared_$1")}\n*{box-sizing:border-box}body{margin:0}.tableRoot{padding:0}.fixtureTile{width:100%;aspect-ratio:16/9}</style><main class="tableRoot"><section class="table" data-playing="true" data-furniture="true" data-round-table="true" data-table-surface="pine" style="--available-table-height:${height-25}px"><div class="tableTop"><div></div><div class="center"><div class="trickField"><div class="widow"><span class="tableCard" style="aspect-ratio:2/3"></span></div></div></div><div></div></div><div class="bottomArea" style="--hand-count:12;--hand-breaks:3"><div class="fixtureTile seat bottom"></div><div class="handColumn"><div class="claimButton"><button>Все мои</button></div><div class="ownHand" data-own-hand="true"><div class="handRow">${cards}</div></div></div><div class="bottomFurniture" data-radio-dock="true"><div class="objects"><button class="radioButton"><svg class="radioArt" viewBox="0 0 420 174"></svg></button></div></div></div></section></main>`);
    const readBounds=()=>page.evaluate(()=>{const get=(s:string)=>document.querySelector(s)!.getBoundingClientRect();const a=get(".fixtureTile"),r=get(".radioButton"),c=get(".cardWithSort:last-child"),f=get(".trickField"),w=get(".widow");return {x:a.left,y:a.bottom,radio:r.left,card:c.right,fieldTop:f.top,widowTop:w.top,table:get(".table").bottom};});
    const start=await readBounds();
    expect(start.card).toBeLessThanOrEqual(start.radio+1);
    expect(start.table).toBeLessThanOrEqual(height);
    expect(start.widowTop).toBeGreaterThanOrEqual(start.fieldTop-1);
    await page.evaluate(()=>{document.querySelectorAll(".cardWithSort").forEach((el,i)=>{if(i>2)el.remove();});const b=document.querySelector<HTMLElement>(".bottomArea")!;b.style.setProperty("--hand-count","3");b.style.setProperty("--hand-breaks","0");});
    const end=await readBounds();
    expect(Math.abs(start.x-end.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(start.y-end.y)).toBeLessThanOrEqual(1);
  });
}
