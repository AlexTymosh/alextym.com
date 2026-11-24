import { test, expect } from "@playwright/test";
import { parseRealtimeFrame, retryDelay } from "../../portfolio/preferans/frontend/src/realtime-client";

const room = "a".repeat(32);
const snapshot = {
  type: "snapshot", protocol: 1, server_now_ms: 1000,
  presence: ["online", "online", "reconnecting"],
  view: { room_id: room, version: 7, status: "playing", occupied: [true, true, true], my_seat: 0, room_admin: false },
};

test("realtime frame rejects wrong room, seat, protocol and malformed input", () => {
  expect(parseRealtimeFrame(JSON.stringify(snapshot), room, 0)?.type).toBe("snapshot");
  expect(parseRealtimeFrame(JSON.stringify(snapshot), room, 1)).toBeNull();
  expect(parseRealtimeFrame(JSON.stringify(snapshot), "b".repeat(32), 0)).toBeNull();
  expect(parseRealtimeFrame(JSON.stringify({ ...snapshot, protocol: 2 }), room, 0)).toBeNull();
  expect(parseRealtimeFrame(JSON.stringify({ ...snapshot, presence: ["online"] }), room, 0)).toBeNull();
  expect(parseRealtimeFrame("{", room, 0)).toBeNull();
  expect(parseRealtimeFrame("x".repeat(96_001), room, 0)).toBeNull();
});

test("realtime retry backoff stays bounded during extended outage", () => {
  expect(retryDelay(0, 1)).toBe(1000);
  expect(retryDelay(3, 1)).toBe(8000);
  expect(retryDelay(999, 1)).toBe(120_000);
  expect(retryDelay(999, 0)).toBe(96_000);
});
