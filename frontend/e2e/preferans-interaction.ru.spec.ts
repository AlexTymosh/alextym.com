import { test, expect } from "@playwright/test";
import { animationBetween, bidsInGroup, canHold, mayConcede, orderHand, ownCards, replayWidow, visibleWidow } from "../../portfolio/preferans/frontend/src/interaction-model";
import { isRoomView, type Bid, type Card, type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
const c=(suit:Card["suit"],rank:number):Card=>({suit,rank});
const bid=(level:number,suit:Bid["suit"]):Bid=>({kind:"regular",level,suit});
const room:RoomView={room_id:"a".repeat(32),version:1,status:"playing",my_seat:0,room_admin:true,game_id:"deal",occupied:[true,true,true],phase:"auction",turn:0,hand:[c("S",7),c("H",14),c("S",9)]};
test("legal bid groups and hold use the server projection",()=>{
  const noWidow:Bid={kind:"ten_no_widow",level:10,suit:"H"};
  expect(bidsInGroup([bid(7,"C"),bid(7,null),bid(10,"H"),noWidow],"7")).toEqual([bid(7,"C"),bid(7,null)]);
  expect(bidsInGroup([bid(10,"H"),noWidow],"ten_no_widow")).toEqual([noWidow]);
  expect(canHold({...room,can_say_here:true,high_bid:bid(6,"S")})).toBe(false);
  expect(canHold({...room,can_say_here:false,high_bid:bid(7,"S")})).toBe(false);
  expect(canHold({...room,can_say_here:true,high_bid:bid(7,"S")})).toBe(true);
});
test("grouped sorting, manual order and own twelve cards",()=>{
  expect(orderHand(room.hand!)).toEqual([c("S",9),c("S",7),c("H",14)]);
  expect(orderHand(room.hand!,["14H","9S","7S"])).toEqual([c("H",14),c("S",9),c("S",7)]);
  const hand=Array.from({length:10},(_,i)=>c(i<8?"S":"H",7+i%8));
  const widow=[c("C",11),c("D",12)];
  expect(ownCards({...room,phase:"discard",hand,widow,declarer:0})).toHaveLength(12);
  expect(ownCards({...room,phase:"discard",hand,widow,declarer:1})).toHaveLength(10);
  expect(ownCards({...room,my_seat:null,hand})).toEqual([]);
});
test("widow is shown only from the already-public projection",()=>{
  const widow=[c("C",11),c("D",12)];
  expect(visibleWidow(room)).toEqual({count:2,cards:[]});
  expect(visibleWidow({...room,phase:"discard",widow})).toEqual({count:2,cards:widow});
  expect(visibleWidow({...room,phase:"declare",widow})).toEqual({count:0,cards:[]});
  expect(replayWidow({...room,widow:[]})).toEqual([]);
  expect(visibleWidow({...room,phase:"play",is_passout:true,played_tricks:1,widow})).toEqual({count:1,cards:[widow[1]]});
});
test("concession and animation respect phases and snapshot identity",()=>{
  expect(mayConcede({...room,phase:"declare",declarer:0,legal_contracts:[bid(6,"S")]})).toBe(true);
  expect(mayConcede({...room,phase:"defense_first",declarer:0,contract:bid(6,"S")})).toBe(false);
  expect(mayConcede({...room,phase:"play",declarer:0,contract:bid(6,"S"),played_tricks:1})).toBe(false);
  expect(animationBetween(null,room)).toBeNull();
  expect(animationBetween({...room,game_id:"old",status:"between"},{...room,version:2})).toBe("deal");
});
test("next-deal view rejects wrong deal identity or ambiguous clocks",()=>{
  const next={...room,status:"between",next_deal:{after_game_id:"deal",deadline_ms:10000,remaining_ms:null}};
  expect(isRoomView(next)).toBe(true);
  expect(isRoomView({...next,next_deal:{...next.next_deal,after_game_id:"wrong"}})).toBe(false);
  expect(isRoomView({...next,next_deal:{...next.next_deal,remaining_ms:3000}})).toBe(false);
});
