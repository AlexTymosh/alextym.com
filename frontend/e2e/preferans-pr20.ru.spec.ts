import { expect, test } from "@playwright/test";
import { autoSettlementAllowed, notebookAngle, splitPlayerName } from "../../portfolio/preferans/frontend/src/table-pr20";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
const view:RoomView={room_id:"a".repeat(32),version:1,status:"awaiting_settlement",my_seat:0,room_admin:true,game_id:"deal",occupied:[true,true,true],settlement_options:{regular_choice:false,passout_defaults:["pool","pool","pool"]}};
test("only three readable notebook perspectives",()=>{
  expect([0,1,2,3,-1].map(notebookAngle)).toEqual([0,-90,90,0,90]);
  expect(splitPlayerName("  First  Last Name ")).toEqual(["First","Last Name"]);
  expect(splitPlayerName("Single")).toEqual(["Single",""]);
});
test("automatic settlement only for unambiguous admin projection",()=>{
  expect(autoSettlementAllowed(view)).toBe(true);
  expect(autoSettlementAllowed({...view,room_admin:false})).toBe(false);
  expect(autoSettlementAllowed({...view,settlement_options:undefined})).toBe(false);
  expect(autoSettlementAllowed({...view,settlement_options:{regular_choice:true,passout_defaults:["pool","pool","pool"]}})).toBe(false);
});
