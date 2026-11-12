import { expect, test } from "@playwright/test";

import { purgeDetachedHandoff } from "../lib/handoff-cleanup";

test("attempts backend purge for an abandoned handoff", async () => {
  const purged: string[] = [];
  const success = await purgeDetachedHandoff("hnd_old", async (handoffId) => {
    purged.push(handoffId);
  });

  expect(success).toBe(true);
  expect(purged).toEqual(["hnd_old"]);
});

test("does not call the backend without a handoff ID", async () => {
  let calls = 0;
  const close = async () => {
    calls += 1;
  };

  expect(await purgeDetachedHandoff(null, close)).toBe(false);
  expect(await purgeDetachedHandoff(undefined, close)).toBe(false);
  expect(await purgeDetachedHandoff("", close)).toBe(false);
  expect(calls).toBe(0);
});

test("reports cleanup failure without throwing into the new chat", async () => {
  const success = await purgeDetachedHandoff("hnd_old", async () => {
    throw new Error("Remote session store unavailable");
  });

  expect(success).toBe(false);
});

test("waits for the close request before reporting success", async () => {
  let complete!: () => void;
  const pending = new Promise<void>((resolve) => {
    complete = resolve;
  });
  let settled = false;
  const task = purgeDetachedHandoff("hnd_old", async () => {
    await pending;
  }).then((result) => {
    settled = true;
    return result;
  });

  await Promise.resolve();
  expect(settled).toBe(false);
  complete();
  expect(await task).toBe(true);
});
