import { expect, test } from "@playwright/test";
import { allowedToAct, type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

const base: RoomView = {
  room_id: "0123456789abcdef0123456789abcdef", version: 4, status: "playing",
  occupied: [true, true, true], my_seat: 0, room_admin: true, game_id: "game",
  phase: "auction", turn: 0,
};

test("Preferans vote and lost connection block old player actions", () => {
  expect(allowedToAct(base)).toBe(true);
  const controls = { paused: false, counter: null, undo: null,
    can_request_undo: false, adjustments: [] };
  expect(allowedToAct({ ...base, controls: { ...controls, paused: true } })).toBe(false);
  expect(allowedToAct({ ...base, controls: { ...controls,
    undo: { kind: "auction_bid" as const, requester: 0, deadline_ms: 180000,
      reason: "Ошибся ставкой", votes: {}, can_vote: false },
  } })).toBe(false);
});

test("Preferans room admin role does not grant a player turn", () => {
  expect(allowedToAct({ ...base, turn: 1 })).toBe(false);
  expect(allowedToAct({ ...base, my_seat: null })).toBe(false);
});
