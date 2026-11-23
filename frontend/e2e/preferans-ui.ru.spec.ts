import { test, expect } from "@playwright/test";
import {
  allowedToAct, bidLabel, cardId, cardLabel, isInvitation, isRoomView,
  moveCard, sortedHand, statusMessage, type RoomView,
} from "../../portfolio/preferans/frontend/src/game-model.ru";

const id = "0123456789abcdef0123456789abcdef";
const lobby: RoomView = {
  room_id: id, version: 0, status: "lobby", occupied: [true, false, false],
  my_seat: 0, room_admin: true, game_id: null,
};

test("Preferans contract: only allow-listed room view is recognized", () => {
  expect(isRoomView(lobby)).toBe(true);
  expect(isRoomView({ ...lobby, room_id: "../../secrets" })).toBe(false);
  expect(isRoomView({ ...lobby, occupied: [true] })).toBe(false);
  expect(isRoomView({ ...lobby, version: 1.5 })).toBe(false);
  expect(isRoomView({ ...lobby, my_seat: 7 })).toBe(false);
});

test("Preferans invitation never requires or supplies private hands", () => {
  const safe = { room_id: id, version: 1, status: "lobby", occupied: [true, true, false] };
  expect(isInvitation(safe)).toBe(true);
  expect(isInvitation({ ...safe, status: "playing" })).toBe(false);
});

test("Preferans player cannot act during someone else's turn", () => {
  const own: RoomView = {
    ...lobby, status: "playing", phase: "auction", turn: 0,
  };
  expect(allowedToAct(own)).toBe(true);
  expect(allowedToAct({ ...own, turn: 2 })).toBe(false);
  expect(allowedToAct({ ...own, my_seat: null })).toBe(false);
});

test("Preferans open hand is controlled by the authoritative controller", () => {
  const own: RoomView = { ...lobby, status: "playing", phase: "play", turn: 2, controller: 0 };
  expect(allowedToAct(own)).toBe(true);
  expect(allowedToAct({ ...own, controller: 1 })).toBe(false);
});

test("Preferans sorting is pure and does not mutate card values", () => {
  const cards = [{ suit: "H" as const, rank: 14 }, { suit: "S" as const, rank: 7 }, { suit: "S" as const, rank: 14 }];
  const previous = JSON.stringify(cards);
  const before = sortedHand(cards, []).map(cardId);
  expect(before).toEqual(["14S", "7S", "14H"]);
  const reordered = moveCard(before, "14S", "14H");
  expect(reordered).toEqual(["7S", "14S", "14H"]);
  expect(JSON.stringify(cards)).toBe(previous);
});

test("Preferans labels distinguish bids and suits", () => {
  expect(bidLabel({ kind: "regular", level: 6, suit: "S" })).toContain("♠");
  expect(bidLabel({ kind: "misere", level: null, suit: null })).toBe("Мизер");
  expect(cardLabel({ suit: "H", rank: 14 })).toBe("Т♥");
});

test("Preferans auth and stale-version failures are user-readable", () => {
  expect(statusMessage(401)).toContain("Сессия");
  expect(statusMessage(403)).toContain("доступа");
  expect(statusMessage(409)).toContain("изменилась");
  expect(statusMessage(503)).toContain("Сервер");
});
