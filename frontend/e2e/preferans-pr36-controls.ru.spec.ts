import { expect, test } from "@playwright/test";
import { canRequestUndo, showFirstHand, tableZoomValue, feedbackRemaining } from "../../portfolio/preferans/frontend/src/control-feedback";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

test("table zoom is bounded and independent of game state",()=>{
  expect(tableZoomValue(null)).toBe(100);
  expect(tableZoomValue("bad")).toBe(100);
  expect(tableZoomValue(160)).toBe(130);
  expect(tableZoomValue(20)).toBe(70);
  expect(tableZoomValue("112")).toBe(110);
});

test("first-hand label disappears after the first played card",()=>{
  const view={status:"playing",first_hand:1,played_tricks:0,trick:[]} as unknown as RoomView;
  expect(showFirstHand(view,1)).toBe(true);
  expect(showFirstHand(view,0)).toBe(false);
  expect(showFirstHand({...view,played_tricks:1},1)).toBe(false);
  expect(showFirstHand({...view,trick:[{owner:1,card:{rank:7,suit:"S"}}]},1)).toBe(false);
});

test("counter disables undo and delayed fallback can show results",()=>{
  const view={status:"playing",my_seat:0,controls:{can_request_undo:true}} as unknown as RoomView;
  expect(canRequestUndo(view)).toBe(true);
  const active={...view,controls:{...view.controls,counter:{target:1}}} as unknown as RoomView;
  expect(canRequestUndo(active)).toBe(false);
  expect(feedbackRemaining(100000,130000)).toBe(12000);
  expect(feedbackRemaining(100000,500001)).toBe(0);
});
