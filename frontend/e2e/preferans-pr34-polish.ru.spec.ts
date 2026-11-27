import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { canRaiseOwn, canHint, sharedHint, ownRaiseScope } from "../../portfolio/preferans/frontend/src/defense-hints";
import { notebookEntryLabel, poolEntryText, vistEquation } from "../../portfolio/preferans/frontend/src/notebook-layout";
import { punchGeometry } from "../../portfolio/preferans/frontend/src/notebook-punches";
import { GAG_MISSING_MS, GAG_FOUND_MS, GAG_RETURN_MS, GAG_FAKE_MS, GAG_TOTAL_MS, gagPhase } from "../../portfolio/preferans/frontend/src/gag-model";
import { tableSeats } from "../../portfolio/preferans/frontend/src/table-model";
import type { RoomView, Card } from "../../portfolio/preferans/frontend/src/game-model.ru";

const card:Card={suit:"S",rank:14};
const base:RoomView={room_id:"a".repeat(32),version:7,game_id:"g",status:"playing",phase:"play",my_seat:0,room_admin:false,occupied:[true,true,true],declarer:0,contract:{kind:"regular",level:7,suit:"S"},hand:[card]};
const root=resolve(process.cwd(),"../portfolio/preferans/frontend/src");
const read=(name:string)=>readFileSync(resolve(root,name),"utf8");

test("own raises are local for every seat, never grant disclosure or actions",()=>{
  for(const seat of [0,1,2]){
    const view={...base,my_seat:seat,declarer:seat};
    expect(canRaiseOwn(view,seat,card)).toBe(true);
    expect(canRaiseOwn({...view,phase:"auction"},seat,card)).toBe(true);
    expect(canRaiseOwn({...view,phase:"declare"},seat,card)).toBe(true);
    expect(canHint(view,seat,card)).toBe(false);
    expect(sharedHint(view,seat,card)).toBe(false);
    expect(canRaiseOwn(view,(seat+1)%3,card)).toBe(false);
    expect(canRaiseOwn({...view,hand:[]},seat,card)).toBe(false);
    expect(canRaiseOwn({...view,phase:"discard"},seat,card)).toBe(false);
    expect(canRaiseOwn({...view,phase:"misere_offer"},seat,card)).toBe(false);
    expect(ownRaiseScope({...view,version:8})).toBe(ownRaiseScope(view));
    expect(ownRaiseScope({...view,game_id:"next"})).not.toBe(ownRaiseScope(view));
  }
  expect(canRaiseOwn({...base,is_passout:true},0,card)).toBe(true);
  expect(canRaiseOwn({...base,my_seat:null},0,card)).toBe(false);
  expect(canRaiseOwn({...base,status:"closed"},0,card)).toBe(false);
});

test("ledger entries end with a full stop without changing values or final arithmetic",()=>{
  expect([0,5,7,10,17].map(n=>notebookEntryLabel(String(n))).join(" ")).toBe("0. 5. 7. 10. 17.");
  expect(notebookEntryLabel(poolEntryText([4,20],1,20))).toBe("<<20>>.");
  expect(vistEquation(32,10)).toEqual([{label:"32 +"},{label:"10",underline:true},{label:"= 42"}]);
});

test("enlarged final badges move along the same sector boundary",()=>{
  for(const seat of [0,1,2]){
    const seats=tableSeats(seat), w=732,cy=322,inner=156,innerY=556;
    for(const side of [seats.left,seats.right]){
      const g=punchGeometry({from:side,to:seats.bottom,bare:0,ordinary:2},seats,w,cy,inner,innerY);
      expect(g.center.y).toBeCloseTo(cy+21+(innerY-cy-21)*.531,8);
      expect(g.end.y).toBeGreaterThan(g.start.y);
      expect(Math.hypot(g.center.x-g.end.x,g.center.y-g.end.y)).toBeCloseTo(63,8);
    }
  }
});

test("gag shows complaint for two seconds and leaves time for discovery and a complete deal",()=>{
  expect(GAG_FOUND_MS-GAG_MISSING_MS).toBe(2000);
  expect(GAG_RETURN_MS-GAG_FOUND_MS).toBeGreaterThanOrEqual(1200);
  expect(GAG_FAKE_MS-GAG_RETURN_MS).toBeGreaterThanOrEqual(1200);
  expect(GAG_TOTAL_MS-GAG_FAKE_MS).toBeGreaterThanOrEqual(3650);
  const mark={seat:0,at_ms:1000};
  expect(gagPhase(mark,1000+GAG_FAKE_MS-1)).toBe("fake");
  expect(gagPhase(mark,1000+GAG_FAKE_MS)).toBe("deal");
  expect(gagPhase(mark,1000+GAG_TOTAL_MS)).toBeNull();
});

test("new material maps are local and recorded with their original asset sizes",()=>{
  const provenance=JSON.parse(read("materials/PROVENANCE.json"));
  const css=read("preferans-table.module.css");
  for(const key of ["walnut","marble","leather"]){
    const data=readFileSync(resolve(root,`materials/${key}.jpg`));
    expect(data.subarray(0,2).toString("hex")).toBe("ffd8");
    expect(data.length).toBe(provenance[key].size);
    expect(css).toContain(`url('./materials/${key}.jpg')`);
  }
});

test("compact reward box, eyes and disposal scene stay bounded on a small landscape table",async({page})=>{
  await page.setViewportSize({width:800,height:450});
  await page.setContent(`<style>${read("preferans-game.module.css")}\n${read("preferans-table.module.css")}\n*{box-sizing:border-box}body{margin:0}.fixture{position:relative;width:350px;height:250px;container-type:size}</style><main class="tableRoot"><div class="table fixture" data-center-choice="true"><div class="trickField" style="width:300px;height:250px"><div class="fieldStatus"><div class="settlementChoice"><strong>Куда записать</strong><section><div class="rewardRoute"><div><button aria-pressed="true">В пулю</button><button>С горы</button></div></div><button>Рассчитать</button></section></div></div></div></div></main>`);
  const field=(await page.locator(".trickField").boundingBox())!,choice=(await page.locator(".settlementChoice").boundingBox())!;
  expect(choice.width).toBeLessThan(field.width);
  expect(Math.abs(choice.x+choice.width/2-field.x-field.width/2)).toBeLessThan(2);
  expect(choice.height).toBeLessThanOrEqual(field.height);
});
