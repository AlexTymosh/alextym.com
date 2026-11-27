import { expect, test } from "@playwright/test";
import { canHint, sharedHint } from "../../portfolio/preferans/frontend/src/defense-hints";
import { awardedMessage, pauseMessage } from "../../portfolio/preferans/frontend/src/play-status.ru";
import { animateDeal, flightDelta } from "../../portfolio/preferans/frontend/src/table-motion";
import type { RoomView, Card } from "../../portfolio/preferans/frontend/src/game-model.ru";

const card:Card={suit:"S",rank:14};
const base:RoomView={room_id:"a".repeat(32),version:10,game_id:"g",status:"playing",phase:"play",my_seat:1,room_admin:false,occupied:[true,true,true],declarer:0,contract:{kind:"misere",level:null,suit:null},hand:[card],open_hands:[{seat:1,cards:[card]}],defense_hints:[]};
test("cues never disclose a hidden card or give declarer access",()=>{
  expect(canHint(base,1,card)).toBe(true);
  expect(sharedHint(base,1,card)).toBe(true);
  expect(canHint({...base,open_hands:[]},1,card)).toBe(true);
  expect(sharedHint({...base,open_hands:[]},1,card)).toBe(false);
  expect(canHint({...base,my_seat:0},1,card)).toBe(false);
  expect(canHint(base,2,card)).toBe(false);
  expect(canHint({...base,phase:"auction"},1,card)).toBe(false);
});
test("claim status displays newly awarded tricks only",()=>{
  const view:RoomView={...base,status:"awaiting_settlement",phase:"finished",tricks_won:[2,8,0],claim:{seat:1,status:"accepted",voters:[0,2],approved:[0,2],rejected_by:null,awarded:6,cards:[]}};
  expect(awardedMessage(view,seat=>`Игрок ${seat+1}`)).toBe("Игрок 2: +6 взяток");
  expect(pauseMessage({...base,controls:{paused:true,pause_reasons:["connection_lost"],counter:null,undo:null,can_request_undo:false,adjustments:[]}},["online","online","reconnecting"],seat=>`Игрок ${seat+1}`)).toContain("Игрок 3");
});
test("packet animation lands in raw order before sorting",async({page})=>{
  await page.setContent(`<div id="table"><div data-play-field style="position:absolute;left:20px;top:20px;width:80px;height:50px"></div><div data-seat="0" data-position="bottom"></div><div data-seat="1" data-position="left"></div><div data-seat="2" data-position="right"></div><div data-own-hand style="position:absolute;left:200px;top:200px;display:flex;gap:12px">${["14S","13S","8H","7H"].map(id=>`<div data-hand-card style="position:relative"><button data-card="${id}" style="width:40px;height:60px">${id}</button></div>`).join("")}</div></div>`);
  await page.addScriptTag({content:`const center=r=>({x:r.left+r.width/2,y:r.top+r.height/2});const flightDelta=${flightDelta.toString()};const DEAL_FLIGHT_MS=900,DEAL_SORT_AT_MS=3100,DEAL_SORT_MS=450;window.cleanup=(${animateDeal.toString()})(document.getElementById('table'),2,['8H','14S','7H','13S']);`});
  const offsets=await page.locator("[data-card]").evaluateAll(cards=>cards.map(card=>({id:(card as HTMLElement).dataset.card,frames:card.getAnimations()[0]?.effect instanceof KeyframeEffect?(card.getAnimations()[0].effect as KeyframeEffect).getKeyframes():[]})));
  expect(offsets.every(c=>c.frames.length===4)).toBe(true);
  expect(offsets.find(c=>c.id==="8H")!.frames[1].transform).not.toBe("translate3d(0px, 0px, 0px)");
  expect(offsets.every(c=>c.frames[3].transform==="none")).toBe(true);
  await page.evaluate(()=>{(window as unknown as {cleanup:()=>void}).cleanup();});
  expect(await page.locator("[data-card]").evaluateAll(cards=>cards.every(card=>card.getAnimations().length===0))).toBe(true);
});
