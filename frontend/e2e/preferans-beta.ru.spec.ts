import { expect, test } from "@playwright/test";
import { activityProgress, effectiveOpacity, parseTransparency, roomAgeMinutes } from "../../portfolio/preferans/frontend/src/table-details";
import { safeDirectory } from "../../portfolio/preferans/frontend/src/table-model";
import { visibleWidow } from "../../portfolio/preferans/frontend/src/interaction-model";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

test("activity progress saturates after 180 seconds without affecting game logic",()=>{
  expect(activityProgress(undefined,1000)).toBe(0);
  expect(activityProgress(1000,0)).toBe(0);
  expect(activityProgress(1000,91_000)).toBe(50);
  expect(activityProgress(1000,181_000)).toBe(100);
  expect(activityProgress(1000,300_000)).toBe(100);
});
test("surface opacity is independent from theme and old glass preference remains readable",()=>{
  expect(parseTransparency("35")).toBe(35);
  for(const bad of [null,"","NaN","100","-5","12"])expect(parseTransparency(bad)).toBeNull();
  expect(effectiveOpacity("glass",null)).toBe(.5);
  expect(effectiveOpacity("felt",null)).toBe(.25);
  expect(effectiveOpacity("blue",40)).toBe(.6);
  expect(effectiveOpacity("wood",0)).toBe(1);
});
test("directory names are safe and age is a local calculation",()=>{
  const room={room_id:"a".repeat(32),status:"lobby",occupied:[true,true,false],mine:true,player_names:["Alice","secret@example.test","Not seated"],created_at_ms:1000};
  expect(safeDirectory({rooms:[room],can_create:true,truncated:false})?.rooms[0].player_names).toEqual(["Alice",null,null]);
  expect(roomAgeMinutes(1000,121_000)).toBe(2);
  expect(roomAgeMinutes(2000,1000)).toBe(0);
  expect(roomAgeMinutes(null,1000)).toBeNull();
});
test("first passout trick displays one known card and a back, never a second face",()=>{
  const view:RoomView={room_id:"a".repeat(32),version:3,status:"playing",occupied:[true,true,true],my_seat:0,room_admin:false,game_id:"deal",phase:"play",is_passout:true,played_tricks:0,widow:[{rank:7,suit:"S"}]};
  expect(visibleWidow(view)).toEqual({count:2,cards:[{rank:7,suit:"S"}]});
  expect(visibleWidow({...view,widow:[]})).toEqual({count:2,cards:[]});
});
