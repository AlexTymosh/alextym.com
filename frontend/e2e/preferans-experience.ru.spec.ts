import { expect, test } from "@playwright/test";
import { isRoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const base={room_id:"a".repeat(32),version:1,status:"playing",my_seat:0,room_admin:true,occupied:[true,true,true],game_id:"deal"};
test("experience projection rejects invalid theme and timing",()=>{
  expect(isRoomView({...base,table_theme:"glass",activity_started_at_ms:123})).toBe(true);
  expect(isRoomView({...base,table_theme:"url(example)"})).toBe(false);
  expect(isRoomView({...base,activity_started_at_ms:-1})).toBe(false);
  expect(isRoomView({...base,last_won_tricks:[null,null,null]})).toBe(true);
  expect(isRoomView({...base,my_seat:null,last_won_tricks:[null,null,null]})).toBe(false);
});
test("all 32 licensed faces are installed locally",()=>{
  for(const suit of ["S","C","D","H"])for(let rank=7;rank<=14;rank++)expect(existsSync(resolve(process.cwd(),`public/preferans/atlas/${rank}${suit}.png`))).toBe(true);
});

import { attachCardPointerDrag } from "../../portfolio/preferans/frontend/src/pointer-drag";
import { animationBetween } from "../../portfolio/preferans/frontend/src/interaction-model";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

test("pointer ghost dispatches one validated drop and removes itself",async({page})=>{
  await page.setContent('<div data-table-view><button data-card="7S" draggable="true" style="width:70px;height:100px;touch-action:none">card</button><div id="target" style="position:absolute;left:180px;top:140px;width:100px;height:100px">target</div></div>');
  await page.addScriptTag({content:`(${attachCardPointerDrag.toString()})(document); document.getElementById("target").addEventListener("drop",()=>{document.body.dataset.drops=String(Number(document.body.dataset.drops||0)+1)});`});
  await page.mouse.move(40,40);await page.mouse.down();await page.mouse.move(220,175,{steps:10});await page.mouse.up();
  await expect(page.locator("body")).toHaveAttribute("data-drops","1");
  await expect(page.locator("[data-pointer-dragging]")).toHaveCount(0);
});
test("coalesced snapshots still display the completed trick",()=>{
  const before:RoomView={...base,status:"playing",phase:"play",played_tricks:0,trick:[]};
  const after:RoomView={...before,version:2,played_tricks:1,last_trick_winner:0,last_trick:[{owner:0,card:{suit:"H",rank:14}},{owner:1,card:{suit:"H",rank:9}},{owner:2,card:{suit:"H",rank:7}}]};
  expect(animationBetween(before,after)).toBe("trick");
});
