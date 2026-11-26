import { expect,test } from "@playwright/test";
import { actualTrickCount } from "../../portfolio/preferans/frontend/src/claim-model";
import { allowedToAct,isRoomView,type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { autoSettlementAllowed } from "../../portfolio/preferans/frontend/src/table-pr20";
import { actorSeat } from "../../portfolio/preferans/frontend/src/table-model";
const base:RoomView={room_id:"a".repeat(32),version:1,status:"playing",my_seat:0,room_admin:true,game_id:"deal",occupied:[true,true,true],phase:"play",turn:0,controller:0};

test("pending claim blocks all card actions and exposes only explicit projection",()=>{
  const view:RoomView={...base,claim:{seat:1,status:"pending",voters:[0,2],approved:[],rejected_by:null,awarded:0,cards:[{suit:"H",rank:14}]}};
  expect(isRoomView(view)).toBe(true);
  expect(allowedToAct(view)).toBe(false);
  expect(actorSeat(view)).toBeNull();
  expect(isRoomView({...view,my_seat:null})).toBe(false);
  expect(isRoomView({...view,claim:{...view.claim,voters:[1]}})).toBe(false);
});
test("awarded remaining tricks do not become fictitious replay bundles",()=>{
  const view:RoomView={...base,status:"awaiting_settlement",phase:"finished",tricks_won:[2,8,0],played_tricks:3,claim:{seat:1,status:"accepted",voters:[0,2],approved:[0,2],rejected_by:null,awarded:7,cards:[]}};
  expect(isRoomView(view)).toBe(true);
  expect(actualTrickCount(view,0)).toBe(2);
  expect(actualTrickCount(view,1)).toBe(1);
  expect(actualTrickCount(view,2)).toBe(0);
});
test("automatic settlement waits for authenticated passout decisions",()=>{
  const view:RoomView={...base,status:"awaiting_settlement",phase:"finished",settlement_options:{regular_choice:false,passout_defaults:["pool","pool","pool"],passout_pending:[1],passout_choices:[[],["pool","hill_first"],[]],passout_targets:[[],[],[]]}};
  expect(isRoomView(view)).toBe(true);
  expect(autoSettlementAllowed(view)).toBe(false);
  expect(autoSettlementAllowed({...view,settlement_options:{...view.settlement_options!,passout_pending:[]}})).toBe(true);
});
