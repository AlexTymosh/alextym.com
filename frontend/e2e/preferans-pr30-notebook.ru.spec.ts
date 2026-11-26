import { expect,test } from "@playwright/test";
import { packNotebookRows,poolEntryText,tokenWidth,vistEquation } from "../../portfolio/preferans/frontend/src/notebook-layout";
import { isRoomView, type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { claimVoteLabels } from "../../portfolio/preferans/frontend/src/claim-copy.ru";

test("empty notebook has no bare entries and long cells wrap without losing order",()=>{
  expect(packNotebookRows([],176)).toEqual([]);
  const tokens=Array.from({length:200},(_,i)=>({label:`. ${i}`,manual:i===20,latest:i===199}));
  const rows=packNotebookRows(tokens,176);
  expect(rows.length).toBeGreaterThan(1);
  expect(rows.flat()).toEqual(tokens);
  for(const row of rows)expect(row.length===1||row.reduce((sum,t)=>sum+tokenWidth(t),0)<=176).toBe(true);
  expect(poolEntryText([12,18,20],2,20)).toBe("<<20>>");
  expect(poolEntryText([12,18],1,20)).toBe("18");
  expect(vistEquation(32,10)).toEqual([{label:"32 +"},{label:"10",underline:true},{label:"= 42"}]);
});
const base:RoomView={room_id:"a".repeat(32),version:4,status:"playing",my_seat:0,room_admin:true,game_id:"deal",occupied:[true,true,true],phase:"play",declarer:0,contract:{kind:"misere",level:null,suit:null}};
test("misere offer capability is limited to seated live players",()=>{
  expect(isRoomView({...base,can_offer_misere:true})).toBe(true);
  expect(isRoomView({...base,can_offer_misere:true,my_seat:null})).toBe(false);
  expect(isRoomView({...base,can_offer_misere:true,phase:"auction"})).toBe(false);
  expect(claimVoteLabels({...base,is_passout:true},1).reject).toBe("Я против! (отэто я гоню...)");
});
test("final hill amounts are validated and legacy reveal is rejected",()=>{
  const v:RoomView={...base,status:"closed",phase:"finished",final_settlement:{pairs:[[0,18,24],[-18,0,10],[-24,-10,0]],net:[42,-8,-34]},final_hill_vists:[0,10,20]};
  expect(isRoomView(v)).toBe(true);
  expect(isRoomView({...v,final_hill_vists:[0,-1,20]})).toBe(false);
  expect(isRoomView({...base,reveal:{}})).toBe(false);
});
