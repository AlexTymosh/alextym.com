import { expect, test } from "@playwright/test";

import { chatHandoffCopy, chatShellCopy } from "../content/chat";

const streamHeaders = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache",
};

test("concurrent SSE closure and POST close render one terminal notice", async ({ page }) => {
  await page.addInitScript(() => {
    type Listener = (event: Event) => void;
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      private listeners = new Map<string, Listener[]>();
      private closed = false;

      constructor() {
        FakeEventSource.instances.push(this);
      }

      addEventListener(name: string, callback: EventListenerOrEventListenerObject) {
        const listener: Listener = (event) => {
          if (typeof callback === "function") {
            callback(event);
          } else {
            callback.handleEvent(event);
          }
        };
        this.listeners.set(name, [...(this.listeners.get(name) ?? []), listener]);
      }

      close() {
        this.closed = true;
      }

      emitServerClose() {
        if (this.closed) {
          return;
        }
        const event = new MessageEvent("closed", {
          data: JSON.stringify({ reason: "session_closed" }),
        });
        for (const listener of this.listeners.get("closed") ?? []) {
          listener(event);
        }
      }
    }

    (window as unknown as { EventSource: typeof EventSource }).EventSource =
      FakeEventSource as unknown as typeof EventSource;
    (window as unknown as { emitServerClose: () => void }).emitServerClose =
      () => FakeEventSource.instances.at(-1)?.emitServerClose();
  });

  await page.route("**/api/warmup", async (route) => {
    await route.fulfill({ status: 200, json: { status: "ok" } });
  });
  await page.route("**/api/chat/stream", async (route) => {
    await route.fulfill({
      status: 200,
      headers: streamHeaders,
      body: [
        "event: meta",
        'data: {"request_id":"req_close_race","status":"started"}',
        "",
        "event: token",
        'data: {"text":"A human can help."}',
        "",
        "event: sources",
        'data: {"sources":[]}',
        "",
        "event: done",
        'data: {"request_id":"req_close_race","confidence":"low","not_enough_data":true,"retrieval_status":"empty","handoff_suggested":true,"handoff_reason":"insufficient_data"}',
        "",
        "",
      ].join("\n"),
    });
  });
  await page.route("**/api/escalations", async (route) => {
    await route.fulfill({
      status: 200,
      json: { status: "ok", handoff_id: "hnd_close_race", state: "waiting_for_alex" },
    });
  });

  let notifyCloseStarted!: () => void;
  const closeStarted = new Promise<void>((resolve) => { notifyCloseStarted = resolve; });
  let releaseClose!: () => void;
  const closePermit = new Promise<void>((resolve) => { releaseClose = resolve; });
  await page.route("**/api/escalations/hnd_close_race/close", async (route) => {
    notifyCloseStarted();
    await closePermit;
    await route.fulfill({ status: 200, json: { status: "ok", state: "closed" } });
  });

  await page.goto("/chat");
  await page.getByLabel(chatShellCopy.inputAriaLabel).fill("Speak to a human");
  await page.getByRole("button", { name: chatShellCopy.sendLabel }).click();
  await expect(
    page.getByRole("button", { name: chatShellCopy.handoffConnectLabel }),
  ).toBeVisible();
  await page.getByRole("button", { name: chatShellCopy.handoffConnectLabel }).click();
  await expect(
    page.getByRole("button", { name: chatShellCopy.handoffCloseLabel }),
  ).toBeVisible();
  await page.getByRole("button", { name: chatShellCopy.handoffCloseLabel }).click();
  await closeStarted;

  await page.evaluate(() => {
    (window as unknown as { emitServerClose: () => void }).emitServerClose();
  });
  await expect(page.getByText(chatHandoffCopy.closedByUserMessage)).toHaveCount(1);

  releaseClose();
  await expect(page.getByLabel(chatShellCopy.inputAriaLabel)).toBeEnabled();
  await page.getByLabel(chatShellCopy.inputAriaLabel).fill("Another question");
  await expect(page.getByRole("button", { name: chatShellCopy.sendLabel })).toBeEnabled();
  await expect(page.getByText(chatHandoffCopy.closedByUserMessage)).toHaveCount(1);
});
