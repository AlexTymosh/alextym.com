import { expect, test, type Page } from "@playwright/test";

import { chatHandoffCopy, chatShellCopy } from "../content/chat";

const streamHeaders = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache",
};

function chatStreamWithHandoff() {
  return [
    "event: meta",
    'data: {"request_id":"req_race","status":"started"}',
    "",
    "event: token",
    'data: {"text":"Please connect with the owner."}',
    "",
    "event: sources",
    'data: {"sources":[]}',
    "",
    "event: done",
    'data: {"request_id":"req_race","confidence":"low","not_enough_data":true,"retrieval_status":"empty","handoff_suggested":true,"handoff_reason":"insufficient_data"}',
    "",
    "",
  ].join("\n");
}

async function requestHandoff(page: Page) {
  await page.getByLabel(chatShellCopy.inputAriaLabel).fill("Request a human reply");
  await page.getByRole("button", { name: chatShellCopy.sendLabel }).click();
  await expect(page.getByRole("button", { name: chatShellCopy.handoffConnectLabel }))
    .toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/warmup", async (route) => {
    await route.fulfill({ status: 200, json: { status: "ok" } });
  });
  await page.route("**/api/chat/stream", async (route) => {
    await route.fulfill({ status: 200, headers: streamHeaders, body: chatStreamWithHandoff() });
  });
});

test("Reset ignores a handoff connect response that resolves afterward", async ({ page }) => {
  let requestArrived!: () => void;
  const arrived = new Promise<void>((resolve) => { requestArrived = resolve; });
  let releaseReply!: () => void;
  const hold = new Promise<void>((resolve) => { releaseReply = resolve; });
  let routeCompleted!: () => void;
  const completed = new Promise<void>((resolve) => { routeCompleted = resolve; });

  await page.route("**/api/escalations", async (route) => {
    requestArrived();
    await hold;
    try {
      await route.fulfill({ status: 200, json: {
        status: "ok", handoff_id: "hnd_old", state: "waiting_for_alex",
        expires_in_seconds: 7200,
      } });
    } catch {
      // A request cancelled by browser navigation/reset can reject fulfillment.
    } finally {
      routeCompleted();
    }
  });

  await page.goto("/chat");
  await requestHandoff(page);
  await page.getByRole("button", { name: chatShellCopy.handoffConnectLabel }).click();
  await arrived;
  await page.getByRole("button", { name: chatShellCopy.resetLabel }).click();
  releaseReply();
  await completed;
  await page.waitForTimeout(100); // Allow the browser to process a late response, if delivered.

  await expect(page.locator(".message-list .message")).toHaveCount(0);
  await expect(page.getByRole("button", { name: chatShellCopy.handoffCloseLabel }))
    .toHaveCount(0);
  await expect(page.getByLabel(chatShellCopy.inputAriaLabel)).toHaveValue("");
});

test("queued events from an already-closed EventSource cannot revive a reset chat", async ({
  page,
}) => {
  await page.addInitScript(() => {
    type Listener = (event: Event) => void;
    class FakeEventSource {
      private listeners = new Map<string, Listener[]>();

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

      close() {}

      emit(name: string, data: object) {
        for (const callback of this.listeners.get(name) ?? []) {
          callback(new MessageEvent(name, { data: JSON.stringify(data) }));
        }
      }
    }
    const streams: FakeEventSource[] = [];
    const EventSourceProxy = class extends FakeEventSource {
      constructor() {
        super();
        streams.push(this);
      }
    };
    (window as unknown as { EventSource: typeof EventSource }).EventSource =
      EventSourceProxy as unknown as typeof EventSource;
    (window as unknown as { emitStaleHandoff: () => void }).emitStaleHandoff = () => {
      streams[0]?.emit("message", { id: "msg_stale", role: "owner", content: "Late reply" });
      streams[0]?.emit("closed", { reason: "session_closed" });
      streams[0]?.emit("error", {});
    };
  });

  await page.route("**/api/escalations", async (route) => {
    await route.fulfill({ status: 200, json: {
      status: "ok", handoff_id: "hnd_old", state: "waiting_for_alex",
      expires_in_seconds: 7200,
    } });
  });

  await page.goto("/chat");
  await requestHandoff(page);
  await page.getByRole("button", { name: chatShellCopy.handoffConnectLabel }).click();
  await expect(page.getByRole("button", { name: chatShellCopy.handoffCloseLabel }))
    .toBeVisible();
  await page.getByRole("button", { name: chatShellCopy.resetLabel }).click();
  await page.evaluate(() => {
    (window as unknown as { emitStaleHandoff: () => void }).emitStaleHandoff();
  });
  await page.waitForTimeout(100); // Flush React updates from queued EventSource listeners.

  await expect(page.locator(".message-list .message")).toHaveCount(0);
  await expect(page.getByText(chatHandoffCopy.reconnectingNotice)).toHaveCount(0);
  await expect(page.getByText("Late reply")).toHaveCount(0);
  await expect(page.getByRole("button", { name: chatShellCopy.handoffCloseLabel }))
    .toHaveCount(0);
});
