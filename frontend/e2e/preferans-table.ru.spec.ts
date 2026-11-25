import { test, expect } from "@playwright/test";
import { actorSeat, opponentCards, safeDirectory, safeProfiles, seatPosition, tableSeats } from "../../portfolio/preferans/frontend/src/table-model";
import { backSvg, cardArtwork } from "../../portfolio/preferans/frontend/src/atlas-art";
import { isRoomView, cardLabel, type RoomView, type Card, type Suit } from "../../portfolio/preferans/frontend/src/game-model.ru";

const room: RoomView = {room_id:"a".repeat(32),version:1,status:"playing",my_seat:0,room_admin:true,game_id:"deal",occupied:[true,true,true],phase:"auction",turn:0,hand:[{suit:"S",rank:14}],hand_counts:[1,10,9]};
test("table uses clockwise left/right positions for every seat",()=>{
  expect(tableSeats(0)).toEqual({left:1,right:2,bottom:0});
  expect(tableSeats(1)).toEqual({left:2,right:0,bottom:1});
  expect(tableSeats(2)).toEqual({left:0,right:1,bottom:2});
  for (const seat of [0,1,2]) for(const [position,index] of Object.entries(tableSeats(seat))) expect(seatPosition(seat,index)).toBe(position);
  expect(seatPosition(0,4)).toBeNull();
});
test("backs derive only from counts; opened hands come only from projection",()=>{
  expect(opponentCards(room,1)).toEqual({open:null,count:10});
  expect(opponentCards(room,2)).toEqual({open:null,count:9});
  expect(opponentCards(room,0)).toEqual({open:null,count:0});
  const cards:Card[]=[{suit:"D",rank:12}];
  expect(opponentCards({...room,open_hands:[{seat:1,cards}]},1)).toEqual({open:cards,count:1});
  expect(opponentCards({...room,hand_counts:[1,999,9]},1)).toEqual({open:null,count:0});
});
test("actor ring identifies controller and freezes during pause",()=>{
  expect(actorSeat({...room,phase:"play",turn:2,controller:1})).toBe(1);
  expect(actorSeat({...room,phase:"discard",declarer:2,turn:0})).toBe(2);
  expect(actorSeat({...room,controls:{paused:true,counter:null,undo:null,can_request_undo:false,adjustments:[]}})).toBeNull();
});
test("atlas deck has 32 distinct local assets, Russian labels, and one generic back",()=>{
  const faces=(["S","C","D","H"] as Suit[]).flatMap(suit=>Array.from({length:8},(_,i)=>cardArtwork({suit,rank:i+7})));
  expect(new Set(faces).size).toBe(32);
  expect(cardLabel({suit:"S",rank:13})).toContain("К");
  expect(cardLabel({suit:"H",rank:14})).toContain("Т");
  expect(backSvg()).not.toContain("<text");
  expect(cardArtwork({suit:"S",rank:7})).toBe("/preferans/atlas/7S.png");
});
test("profiles and directory reject untrusted fields and URLs",()=>{
  expect(safeProfiles({profiles:[{name:"Player",avatar:"https://example.invalid/a"},{name:"private@example.invalid"},null]})).toEqual([{name:"Player",avatar:null},{name:null,avatar:null},{name:null,avatar:null}]);
  expect(safeDirectory({rooms:[{room_id:"x"}],can_create:true,truncated:false})).toBeNull();
  expect(safeDirectory({rooms:[],can_create:false,truncated:false})).toEqual({rooms:[],can_create:false,truncated:false});
});
test("new lobby projection validates readiness before use",()=>{
  const lobby={...room,status:"lobby",lobby_setup:{ready:[false,true,false],dealer:2,target:20,ruleset:"classic",ruleset_version:1}};
  expect(isRoomView(lobby)).toBe(true);
  expect(isRoomView({...lobby,lobby_setup:{...lobby.lobby_setup,ready:[true]}})).toBe(false);
});
