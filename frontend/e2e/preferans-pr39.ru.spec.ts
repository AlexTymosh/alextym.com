import { expect, test } from "@playwright/test";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { actualTrickCount, validClaim } from "../../portfolio/preferans/frontend/src/claim-model";
import { lobbyReady } from "../../portfolio/preferans/frontend/src/room-preparation";
import { awardedMessage } from "../../portfolio/preferans/frontend/src/play-status.ru";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

test("by-own award counts exclude only agreed tricks from replay history",()=>{
  const view={my_seat:0,declarer:0,phase:"finished",status:"awaiting_settlement",tricks_won:[7,3,0],claim:{seat:0,status:"accepted",voters:[1],approved:[1],rejected_by:null,awarded:8,cards:[],defender_target:3,awards:[6,2,0]}} as unknown as RoomView;
  expect(validClaim(view.claim,view as unknown as Record<string,unknown>)).toBe(true);
  expect([0,1,2].map(i=>actualTrickCount(view,i))).toEqual([1,1,0]);
  expect(awardedMessage(view,i=>`P${i}`)).toBe("P0: +6 взяток · P1: +2 взяток");
  expect(validClaim({...view.claim,awards:[7,2,0]},view as unknown as Record<string,unknown>)).toBe(false);
});
test("first-deal readiness requires all three occupied and consenting seats",()=>{
  const view={status:"lobby",occupied:[true,true,true],lobby_setup:{ready:[true,true,true]}} as unknown as RoomView;
  expect(lobbyReady(view)).toBe(true);
  expect(lobbyReady({...view,occupied:[true,false,true]})).toBe(false);
  expect(lobbyReady({...view,lobby_setup:{...view.lobby_setup!,ready:[true,false,true]}})).toBe(false);
});
test("element scale leaves the table and central card sizes unchanged",async({page})=>{
  await page.setViewportSize({width:1400,height:900});
  const css=readFileSync(resolve(process.cwd(),"../portfolio/preferans/frontend/src/preferans-table.module.css"),"utf8");
  await page.setContent(`<style>${css}</style><div class="tableScene" data-table-zoomed="true" style="--table-zoom:1;width:1100px"><section class="table" data-playing="true" style="--available-table-height:700px"><div class="tableTop"><div class="seat"><div class="avatar"></div></div><div class="center"><div class="trickField"><span class="tableCard">A</span></div></div></div></section></div>`);
  const table=page.locator(".table"), avatar=page.locator(".avatar"), field=page.locator(".trickField"), center=page.locator(".center .tableCard");
  const before=await table.boundingBox(), a=await avatar.boundingBox(), c=await center.boundingBox(), f=await field.boundingBox();
  expect(c!.width).toBeGreaterThan(0);
  await page.locator(".tableScene").evaluate(el=>(el as HTMLElement).style.setProperty("--table-zoom",".7"));
  expect((await table.boundingBox())!.width).toBeCloseTo(before!.width,0);
  expect((await table.boundingBox())!.height).toBeCloseTo(before!.height,0);
  expect((await field.boundingBox())!.width).toBeCloseTo(f!.width,0);
  expect((await avatar.boundingBox())!.width).toBeLessThan(a!.width);
  expect((await center.boundingBox())!.width).toBeCloseTo(c!.width,0);
});
