import { expect, test } from "@playwright/test";
import { DEAL_DURATION_MS, TRICK_DURATION_MS, flightDelta, animateCollection } from "../../portfolio/preferans/frontend/src/table-motion";
import { mayStart, dealerFor } from "../../portfolio/preferans/frontend/src/table-interaction";
import { mayConcede } from "../../portfolio/preferans/frontend/src/interaction-model";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

const base:RoomView={room_id:"a".repeat(32),game_id:"deal",version:1,status:"playing",occupied:[true,true,true],my_seat:1,room_admin:false};
test("next dealer can start without bypassing automatic countdown",()=>{
  const between:RoomView={...base,status:"between",dealer:0};
  expect(dealerFor(between)).toBe(1);
  expect(mayStart(between)).toBe(true);
  expect(mayStart({...between,my_seat:2})).toBe(false);
  expect(mayStart({...between,next_deal:{after_game_id:"deal",deadline_ms:1000,remaining_ms:null}})).toBe(false);
});
test("without three is only a declaration option",()=>{
  const view:RoomView={...base,phase:"declare",declarer:1,winning_bid:{kind:"regular",level:7,suit:"H"},legal_contracts:[{kind:"regular",level:7,suit:"H"}]};
  expect(mayConcede(view)).toBe(true);
  expect(mayConcede({...view,phase:"defense_first"})).toBe(false);
  expect(mayConcede({...view,phase:"play"})).toBe(false);
  expect(mayConcede({...view,winning_bid:{kind:"misere",level:null,suit:null}})).toBe(false);
});
test("motion uses actual geometry rather than fixed directional offsets",()=>{
  const a={left:100,top:100,width:60,height:90} as DOMRect;
  const b={left:400,top:270,width:40,height:60} as DOMRect;
  expect(flightDelta(a,b)).toEqual({x:290,y:155});
  expect(DEAL_DURATION_MS).toBe(3650);
  expect(TRICK_DURATION_MS).toBeGreaterThan(1300);
});
test("collection travels to the winning bundle and clears clones",async({page})=>{
  await page.setContent(`<div id="table"><div data-play-field style="position:absolute;left:100px;top:100px"><div data-trick-seat="0"><span style="display:block;width:40px;height:60px;background:red"></span></div></div><div data-trick-train="1" style="position:absolute;left:400px;top:250px"><button data-latest="true" style="width:40px;height:60px">target</button></div></div>`);
  await page.addScriptTag({content:`const center = r => ({x:r.left+r.width/2,y:r.top+r.height/2}); const flightDelta = ${flightDelta.toString()}; const COLLECT_HOLD_MS=0,COLLECT_FLIGHT_MS=400; window.cleanup = (${animateCollection.toString()})(document.getElementById('table'),1);`});
  await expect(page.locator('body > [inert]')).toHaveCount(1);
  await expect(page.locator('body > [inert]')).toHaveCount(0);
  await page.evaluate(()=>{(window as unknown as {cleanup:()=>void}).cleanup();});
  await expect(page.locator('[data-trick-seat] > span')).toBeVisible();
});
