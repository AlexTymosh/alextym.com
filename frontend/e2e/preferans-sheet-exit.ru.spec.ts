import { expect, test } from "@playwright/test";
import { isRoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

const base = { room_id: "a".repeat(32), version: 5, status: "playing", my_seat: 1, room_admin: false, occupied: [true,true,true], game_id: "deal" };

test("technical finish is terminal and does not deliver remaining cards", () => {
  expect(isRoomView({...base,status:"closed",sheet_loser:1})).toBe(true);
  expect(isRoomView({...base,sheet_loser:1})).toBe(false);
  expect(isRoomView({...base,status:"closed",sheet_loser:"1"})).toBe(false);
  expect(isRoomView({...base,status:"closed",sheet_loser:1,hand:[]})).toBe(false);
});
