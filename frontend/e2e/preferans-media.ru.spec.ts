import { test, expect } from "@playwright/test";
import { isMediaState, recordingMayContinue, RECORDING_WATCHDOG_MS } from "../../portfolio/preferans/frontend/src/media-client";

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


test("local recording fails closed after stale consent, hidden tab or offline", () => {
  const live = { ...base, recording: {
    id: "a".repeat(24), initiator: 0, status: "active" as const,
    votes: [true, true, true],
  }, participants: Array.from({ length: 3 }, () => ({ audio: true, video: false })) };
  expect(recordingMayContinue(live, 0, 1000, 1000 + RECORDING_WATCHDOG_MS, true)).toBe(true);
  expect(recordingMayContinue(live, 0, 1000, 1001 + RECORDING_WATCHDOG_MS, true)).toBe(false);
  expect(recordingMayContinue(live, 0, 1000, 2000, false)).toBe(false);
  expect(recordingMayContinue({ ...live, recording: { ...live.recording, votes: [true, null, true] } }, 0, 1000, 2000, true)).toBe(false);
  expect(recordingMayContinue({ ...live, recording: { ...live.recording, status: "stopped" } }, 0, 1000, 2000, true)).toBe(false);
  expect(recordingMayContinue({ ...live, participants: [live.participants[0], live.participants[1], { audio: false, video: false }] }, 0, 1000, 2000, true)).toBe(false);
  expect(recordingMayContinue(live, 1, 1000, 2000, true)).toBe(false);
});
