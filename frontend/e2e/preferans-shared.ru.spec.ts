import { test, expect } from "@playwright/test";
import { isPresentation, musicPosition, replayMoveAllowed, type Presentation } from "../../portfolio/preferans/frontend/src/presentation-model";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
const p: Presentation={revision:1,enabled:true,server_now_ms:10000,overlay:{kind:"last_trick",id:1,seat:0,game_id:"deal",opened_at_ms:10000},break:null,music:{track:0,playing:true,offset_ms:500,changed_at_ms:10000}};
test("shared projection rejects malformed overlay and private control shapes",()=>{
  expect(isPresentation(p)).toBe(true);
  expect(isPresentation({...p,revision:-1})).toBe(false);
  expect(isPresentation({...p,overlay:{...p.overlay,seat:3}})).toBe(false);
  expect(isPresentation({...p,break:{id:1,ready:[true,true]}})).toBe(false);
  expect(isPresentation({...p,music:{...p.music,track:8}})).toBe(false);
});
test("only a sole last-trick pause permits a card action",()=>{
  const view:RoomView={room_id:"a".repeat(32),version:1,status:"playing",occupied:[true,true,true],my_seat:0,room_admin:true,game_id:"deal",phase:"play",presentation:p,controls:{paused:true,pause_reasons:["shared_overlay"],counter:null,undo:null,can_request_undo:false,adjustments:[]}};
  expect(replayMoveAllowed(view)).toBe(true);
  expect(replayMoveAllowed({...view,controls:{...view.controls!,pause_reasons:["shared_overlay","break"]}})).toBe(false);
  expect(replayMoveAllowed({...view,phase:"auction"})).toBe(false);
  expect(replayMoveAllowed({...view,presentation:{...p,overlay:{...p.overlay!,kind:"radio"}}})).toBe(false);
});
test("music cursor is derived from the server anchor, including after reconnect",()=>{
  expect(musicPosition(p.music,22500)).toEqual({track:1,offset:1000});
  expect(musicPosition(p.music,46500)).toEqual({track:1,offset:1000});
  expect(musicPosition({...p.music,playing:false},46500)).toEqual({track:0,offset:500});
});
