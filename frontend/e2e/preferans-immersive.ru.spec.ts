import { expect, test } from "@playwright/test";
import type { Card, RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { changeDraft, dealerFor, invitationId, legalDrop, matchingDrag, mayPassDeck, mayStart, type DragIntent } from "../../portfolio/preferans/frontend/src/table-interaction";
import { orderHand } from "../../portfolio/preferans/frontend/src/interaction-model";
import { backSvg, themedBackSvg, cardArtwork } from "../../portfolio/preferans/frontend/src/atlas-art";

const room:RoomView={room_id:"a".repeat(32),game_id:"deal",version:5,status:"playing",occupied:[true,true,true],my_seat:0,room_admin:false,phase:"play",turn:1,controller:0,legal_cards:[{suit:"H",rank:14}]};
const drag:DragIntent={kind:"card",id:"14H",owner:1,room:room.room_id,game:room.game_id,version:5};

test("drop is bound to the current authoritative turn and snapshot",()=>{
  expect(legalDrop(room,drag)).toEqual({suit:"H",rank:14});
  expect(legalDrop(room,{...drag,owner:0})).toBeNull();
  expect(legalDrop(room,{...drag,id:"7S"})).toBeNull();
  expect(legalDrop({...room,version:6},drag)).toBeNull();
  expect(legalDrop({...room,controller:2},drag)).toBeNull();
  expect(legalDrop({...room,controls:{paused:true,counter:null,undo:null,adjustments:[],can_request_undo:false}},drag)).toBeNull();
  expect(matchingDrag(drag,{...room,game_id:"another"})).toBe(false);
});

test("two-card draft is reversible without a server action",()=>{
  expect(changeDraft([],"14H",true)).toEqual(["14H"]);
  expect(changeDraft(["14H"],"14H",true)).toEqual(["14H"]);
  expect(changeDraft(["14H","7S"],"8D",true)).toEqual(["14H","7S"]);
  expect(changeDraft(["14H","7S"],"14H",false)).toEqual(["7S"]);
});

test("selected dealer may transfer only before the initial deal",()=>{
  const lobby:RoomView={...room,game_id:null,status:"lobby",lobby_setup:{dealer:0,target:20,ready:[true,true,true],ruleset:"classic",ruleset_version:1}};
  expect(dealerFor(lobby)).toBe(0);
  expect(mayStart(lobby)).toBe(true);
  expect(mayPassDeck(lobby,2)).toBe(true);
  expect(mayPassDeck({...lobby,my_seat:1},2)).toBe(false);
  expect(mayPassDeck(room,2)).toBe(false);
  expect(mayStart({...lobby,lobby_setup:{...lobby.lobby_setup!,ready:[false,true,true]}})).toBe(false);
  expect(mayStart({...lobby,status:"between",dealer:2,lobby_setup:undefined})).toBe(false);
});

test("card group order matches the approved reference and backs are independent",()=>{
  const c=(suit:Card["suit"],rank:number):Card=>({suit,rank});
  const cards=[c("C",7),c("H",7),c("D",8),c("S",9),c("H",14),c("S",14),c("D",10),c("H",10),c("H",8),c("S",11),c("D",13),c("H",13)];
  expect(orderHand(cards).map(c=>`${c.rank}${c.suit}`)).toEqual(["14H","13H","10H","8H","7H","14S","11S","9S","13D","10D","8D","7C"]);
  expect(themedBackSvg("classic")).toBe(backSvg());
  expect(new Set(["classic","ornament","red-blue","green"].map(t=>themedBackSvg(t as "classic"|"ornament"|"red-blue"|"green"))).size).toBe(4);
  const faces=["S","C","D","H"].flatMap(s=>Array.from({length:8},(_,i)=>cardArtwork(c(s as Card["suit"],7+i))));
  expect(new Set(faces).size).toBe(32);
});

test("invitation link is same-origin and room-shaped",()=>{
  const origin="https://example.invalid", id="a".repeat(32);
  expect(invitationId(`${origin}/portfolio/preferans?room=${id}`,origin)).toBe(id);
  expect(invitationId(id,origin)).toBe(id);
  expect(invitationId(`https://other.invalid/portfolio/preferans?room=${id}`,origin)).toBe("");
  expect(invitationId(`${origin}/unrelated?room=${id}`,origin)).toBe("");
});
