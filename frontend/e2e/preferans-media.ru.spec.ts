import { test, expect } from "@playwright/test";
import { isMediaState } from "../../portfolio/preferans/frontend/src/media-client";

const room_id = "0123456789abcdef0123456789abcdef";
const base = {
  room_id, seat: 0, version: 0,
  participants: [
    { audio: false, video: false }, { audio: true, video: false }, { audio: true, video: true },
  ],
  signals: [], recording: null,
};

test("media contract is seat-scoped, typed and independent of private hands", () => {
  expect(isMediaState(base, room_id)).toBe(true);
  expect(isMediaState({ ...base, room_id: "wrong" }, room_id)).toBe(false);
  expect(isMediaState({ ...base, participants: [{ audio: true }] }, room_id)).toBe(false);
  expect(isMediaState({ ...base, signals: [{ sequence: 1, from: 7, kind: "offer", data: {} }] }, room_id)).toBe(false);
  expect(isMediaState({ ...base, version: -2 }, room_id)).toBe(false);
  expect(isMediaState({ ...base, recording: {
    id: "a".repeat(24), initiator: 0, status: "active", votes: [true, true, true],
  } }, room_id)).toBe(true);
  expect(isMediaState({ ...base, recording: {
    id: "a".repeat(24), initiator: 0, status: "active", votes: [true, null, true],
  } }, room_id)).toBe(true);
  expect(isMediaState({ ...base, recording: {
    id: "a".repeat(24), initiator: 0, status: "active", votes: [true, true],
  } }, room_id)).toBe(false);
});
