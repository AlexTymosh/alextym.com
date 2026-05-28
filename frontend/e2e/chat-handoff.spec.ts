import { expect, test } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

const HANDOFF_ID = `hnd_${"a".repeat(32)}`;
const ALEX_REPLY = "Thanks, I can see the website chat.";

test.beforeEach(async ({ page }) => {
  await mockWarmup(page);
});

test("connects the visitor to Alex and forwards follow-up messages", async ({
  page,
}) => {
  let escalationPayload: unknown;
  let visitorMessagePayload: unknown;

  await mockEscalationCreate(page, (payload) => {
    escalationPayload = payload;
  });
  await mockEscalationStream(page, [
    escalationEvent("meta", { handoff_id: HANDOFF_ID, status: "connected" }),
    escalationEvent(
      "message",
      {
        id: "msg_alex_1",
        role: "alex",
        content: ALEX_REPLY,
        created_at: "2026-01-01T00:00:00+00:00",
      },
      "msg_alex_1",
    ),
  ]);
  await mockEscalationMessage(page, (payload) => {
    visitorMessagePayload = payload;
  });

  await page.goto("/chat");
  await requestHumanHandoff(page);

  await expect(page.getByRole("region", { name: "Connect with Alex" })).toBeVisible();

  await page.getByRole("button", { name: /connect me with alex/i }).click();

  await expect.poll(() => escalationPayload).toMatchObject({
    consent_accepted: true,
    reason: "user_requested_human",
  });
  await expect(page.getByText("Alex has been notified")).toBeVisible();
  await expect(page.getByText(ALEX_REPLY)).toBeVisible();
  await expect(page.getByRole("region", { name: "Active handoff" })).toBeVisible();

  const followUpMessage = "I can discuss the role tomorrow.";
  await sendChatMessage(page, followUpMessage);

  await expect.poll(() => visitorMessagePayload).toMatchObject({
    content: followUpMessage,
    company_website: "",
  });
  await expect(page.getByText(followUpMessage)).toBeVisible();
});

test("closes an active handoff and returns the chat to AI mode", async ({
  page,
}) => {
  let closeRequestWasSent = false;

  await mockEscalationCreate(page);
  await mockEscalationStream(page, [
    escalationEvent("meta", { handoff_id: HANDOFF_ID, status: "connected" }),
  ]);
  await mockEscalationClose(page, () => {
    closeRequestWasSent = true;
  });
  await mockAiStream(page, "The AI assistant is active again.");

  await page.goto("/chat");
  await requestHumanHandoff(page);
  await page.getByRole("button", { name: /connect me with alex/i }).click();

  await expect(page.getByRole("region", { name: "Active handoff" })).toBeVisible();
  await page.getByRole("button", { name: /end handoff/i }).click();

  await expect.poll(() => closeRequestWasSent).toBe(true);
  await expect(page.getByText("This handoff has been closed")).toBeVisible();
  await expect(page.getByRole("region", { name: "Active handoff" })).toBeHidden();

  await sendChatMessage(page, "Can you answer as AI again?");
  await expect(page.getByText("The AI assistant is active again.")).toBeVisible();
});

test("allows the visitor to continue with AI without starting handoff", async ({
  page,
}) => {
  await page.goto("/chat");
  await requestHumanHandoff(page);

  await expect(page.getByRole("region", { name: "Connect with Alex" })).toBeVisible();
  await page.getByRole("button", { name: /continue with ai/i }).click();

  await expect(page.getByRole("region", { name: "Connect with Alex" })).toBeHidden();
});

async function requestHumanHandoff(page: Page): Promise<void> {
  await sendChatMessage(page, "connect me with Alex");
}

async function sendChatMessage(page: Page, message: string): Promise<void> {
  await page.getByRole("textbox", { name: /ask alex/i }).fill(message);
  await page.getByRole("button", { name: /send message/i }).click();
}

async function mockWarmup(page: Page): Promise<void> {
  await page.route("**/api/warmup", async (route) => {
    await fulfillJson(route, { status: "warmed" });
  });
}

async function mockEscalationCreate(
  page: Page,
  onPayload?: (payload: unknown) => void,
): Promise<void> {
  await page.route("**/api/escalations", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }

    onPayload?.(route.request().postDataJSON());
    await fulfillJson(route, {
      status: "ok",
      handoff_id: HANDOFF_ID,
      state: "waiting_for_alex",
      expires_in_seconds: 7200,
    });
  });
}

async function mockEscalationMessage(
  page: Page,
  onPayload?: (payload: unknown) => void,
): Promise<void> {
  await page.route(`**/api/escalations/${HANDOFF_ID}/messages`, async (route) => {
    onPayload?.(route.request().postDataJSON());
    await fulfillJson(route, { status: "ok" });
  });
}

async function mockEscalationClose(
  page: Page,
  onClose?: () => void,
): Promise<void> {
  await page.route(`**/api/escalations/${HANDOFF_ID}/close`, async (route) => {
    onClose?.();
    await fulfillJson(route, { status: "ok", state: "closed" });
  });
}

async function mockEscalationStream(
  page: Page,
  events: string[],
): Promise<void> {
  await page.route(`**/api/escalations/${HANDOFF_ID}/stream`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream; charset=utf-8",
      },
      body: events.join("") || ": heartbeat\n\n",
    });
  });
}

async function mockAiStream(page: Page, answer: string): Promise<void> {
  await page.route("**/api/chat/stream", async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream; charset=utf-8",
      },
      body: [
        escalationEvent("meta", { request_id: "req_test" }),
        escalationEvent("token", { text: answer }),
        escalationEvent("sources", { sources: [] }),
        escalationEvent("done", {
          confidence: "low",
          not_enough_data: false,
        }),
      ].join(""),
    });
  });
}

function escalationEvent(
  event: string,
  data: Record<string, unknown>,
  id?: string,
): string {
  const lines = [];
  if (id) {
    lines.push(`id: ${id}`);
  }
  lines.push(`event: ${event}`);
  lines.push(`data: ${JSON.stringify(data)}`);
  return `${lines.join("\n")}\n\n`;
}

async function fulfillJson(
  route: Route,
  body: Record<string, unknown>,
  status = 200,
): Promise<void> {
  await route.fulfill({
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
    },
    body: JSON.stringify(body),
  });
}
