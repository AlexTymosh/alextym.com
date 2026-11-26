import { expect, test } from "@playwright/test";
import { allowedToAct, isRoomView, type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { canHold } from "../../portfolio/preferans/frontend/src/interaction-model";

const base:RoomView={room_id:"a".repeat(32),version:1,status:"playing",my_seat:1,room_admin:false,game_id:"deal",occupied:[true,true,true]};
test("here is server-authorized and never holds six spades",()=>{
  const bid={kind:"regular",level:7,suit:"C"} as const;
  expect(canHold({...base,phase:"auction",high_bid:bid,can_say_here:true})).toBe(true);
  expect(canHold({...base,phase:"auction",high_bid:bid,can_say_here:false})).toBe(false);
  expect(canHold({...base,phase:"auction",high_bid:{kind:"regular",level:6,suit:"S"},can_say_here:true})).toBe(false);
  for(const kind of ["misere","misere_no_widow"] as const)expect(canHold({...base,phase:"auction",high_bid:{kind,level:null,suit:null},can_say_here:true})).toBe(false);
});
test("both misere defenders may vote independently",()=>{
  const view:RoomView={...base,phase:"misere_offer",declarer:0,turn:2,misere_offer:{approved:[],can_vote:true}};
  expect(isRoomView(view)).toBe(true);
  expect(allowedToAct(view)).toBe(true);
  expect(allowedToAct({...view,misere_offer:{approved:[1],can_vote:false}})).toBe(false);
  expect(isRoomView({...view,misere_offer:{approved:[0],can_vote:true}})).toBe(false);
  expect(isRoomView({...view,my_seat:0})).toBe(false);
});

test("final notebook validates signed reconciled balances",()=>{
  const final={...base,status:"closed" as const,final_settlement:{pairs:[[0,18,24],[-18,0,10],[-24,-10,0]],net:[42,-8,-34]}};
  expect(isRoomView(final)).toBe(true);
  expect(isRoomView({...final,status:"playing"})).toBe(false);
  expect(isRoomView({...final,my_seat:null})).toBe(false);
  expect(isRoomView({...final,final_settlement:{...final.final_settlement,net:[41,-8,-34]}})).toBe(false);
});
