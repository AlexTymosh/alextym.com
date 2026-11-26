import { test, expect } from "@playwright/test";
import { FirebaseQuotaCircuit, isFirebaseQuota } from "../lib/portfolio-lab/firestore-quota";
import { fallbackDelay, RequestCooldown } from "../../portfolio/preferans/frontend/src/transport-budget";

test("quota circuit does not cache permission or extend on concurrent failure", async () => {
  let at = 1000;
  const circuit = new FirebaseQuotaCircuit(() => at);
  expect(isFirebaseQuota({ code: 7 })).toBe(false);
  expect(circuit.observe({ code: 8 })).toBe(true);
  expect(circuit.remaining()).toBe(120);
  at += 10_000;
  circuit.observe({ code: 8 });
  expect(circuit.remaining()).toBe(110);
  expect(await circuit.run(async () => true).catch(() => false)).toBe(false);
  at += 110_000;
  expect(await circuit.run(async () => true)).toBe(true);
  circuit.observe({ code: 8 });
  expect(circuit.remaining()).toBe(240);
});

test("fallback traffic is bounded and honors retry-after", () => {
  expect(fallbackDelay("playing", false)).toBe(15_000);
  expect(fallbackDelay("lobby", false)).toBe(30_000);
  expect(fallbackDelay("playing", true)).toBe(60_000);
  expect(fallbackDelay("playing", false, 100)).toBe(120_000);
  let at = 0;
  const circuit = new RequestCooldown(() => at);
  circuit.observe(403, "120");
  expect(circuit.remaining()).toBe(0);
  circuit.observe(503, "120");
  expect(circuit.remaining()).toBe(120_000);
  at += 15_000;
  circuit.observe(503, null);
  expect(circuit.remaining()).toBe(105_000);
  at += 105_000;
  expect(circuit.remaining()).toBe(0);
});
