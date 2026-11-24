import { expect, test } from "@playwright/test";
import { isRoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { isSheetOffers } from "../../portfolio/preferans/frontend/src/sheet-exit-model";

const base = { room_id: "a".repeat(32), version: 5, status: "playing", my_seat: 1, room_admin: false, occupied: [true,true,true], game_id: "deal" };
const offer = {id: 5, from: 0, to: 1};

test("sheet offer projection is bounded and seat-scoped", () => {
  expect(isRoomView({...base, sheet_offers:[offer]})).toBe(true);
  expect(isSheetOffers([offer, {...offer, id:6}])).toBe(false);
  expect(isSheetOffers([{...offer, from:1}])).toBe(false);
  expect(isSheetOffers([{...offer, uid:"secret"}])).toBe(false);
  expect(isRoomView({...base, my_seat:null, sheet_offers:[offer]})).toBe(false);
  expect(isRoomView({...base, status:"closed", sheet_offers:[offer]})).toBe(false);
});

test("technical finish is terminal and does not deliver remaining cards", () => {
  expect(isRoomView({...base,status:"closed",sheet_loser:1})).toBe(true);
  expect(isRoomView({...base,sheet_loser:1})).toBe(false);
  expect(isRoomView({...base,status:"closed",sheet_loser:"1"})).toBe(false);
  expect(isRoomView({...base,status:"closed",sheet_loser:1,hand:[]})).toBe(false);
});
