import { expect, test, type Page } from "@playwright/test";
import { chatNoticeCopy, chatShellCopy } from "../content/chat";

const streamHeaders = {
  "Cache-Control": "no-cache",
  "Content-Type": "text/event-stream",
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/warmup", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 200,
      body: JSON.stringify({ status: "ok" }),
    });
  });
});

test("shows backend SSE error events to the user", async ({ page }) => {
  await page.route("**/api/chat/stream", async (route) => {
    await route.fulfill({
      headers: streamHeaders,
      status: 200,
      body: buildSseStream([
        ["meta", { request_id: "req_stream_error", status: "started" }],
        ["error", { message: chatNoticeCopy.assistantErrorMessage }],
      ]),
    });
  });
  await page.route("**/api/chat", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 500,
      body: JSON.stringify({ detail: "fallback should not hide stream errors" }),
    });
  });

  await page.goto("/chat");
  await askQuestion(page, "Trigger a stream error.");

  await expect(
    page.locator(".message--assistant .message__content").last(),
  ).toContainText(chatNoticeCopy.assistantErrorMessage);
  await expect(page.getByText(chatNoticeCopy.assistantUnavailable)).toBeVisible();
  await expect(page.getByText(chatShellCopy.handoffPromptTitle)).toHaveCount(0);
});

test("marks a partial stream as incomplete when it closes before done", async ({
  page,
}) => {
  const partialAnswer = "Alex builds automation systems";

  await page.route("**/api/chat/stream", async (route) => {
    await route.fulfill({
      headers: streamHeaders,
      status: 200,
      body: buildSseStream([
        ["meta", { request_id: "req_partial_stream", status: "started" }],
        ["token", { text: partialAnswer }],
        ["sources", { sources: [] }],
      ]),
    });
  });
  await page.route("**/api/chat", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 200,
      body: JSON.stringify({
        answer: "This fallback answer must not replace a partial stream.",
        sources: [],
        confidence: "low",
        not_enough_data: false,
        retrieval_status: "success",
        handoff_suggested: false,
        handoff_reason: null,
      }),
    });
  });

  await page.goto("/chat");
  await askQuestion(page, "Trigger a partial stream.");

  const assistantMessage = page
    .locator(".message--assistant .message__content")
    .last();
  await expect(assistantMessage).toContainText(partialAnswer);
  await expect(assistantMessage).not.toContainText(
    "This fallback answer must not replace a partial stream.",
  );
  await expect(page.getByText(chatNoticeCopy.streamingEndedEarly)).toBeVisible();
  await expect(page.getByText(chatShellCopy.handoffPromptTitle)).toHaveCount(0);
});

test("does not leave an empty assistant response when a stream ends before done", async ({
  page,
}) => {
  await page.route("**/api/chat/stream", async (route) => {
    await route.fulfill({
      headers: streamHeaders,
      status: 200,
      body: buildSseStream([
        ["meta", { request_id: "req_empty_incomplete", status: "started" }],
      ]),
    });
  });
  await page.route("**/api/chat", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 500,
      body: JSON.stringify({ detail: "fallback unavailable" }),
    });
  });

  await page.goto("/chat");
  await askQuestion(page, "Trigger an empty incomplete stream.");

  await expect(
    page.locator(".message--assistant .message__content").last(),
  ).toContainText(chatNoticeCopy.assistantErrorMessage);
  await expect(page.getByText(chatNoticeCopy.assistantUnavailable)).toBeVisible();
  await expect(
    page.getByText("Understanding your question.", { exact: true }),
  ).toHaveCount(0);
});

async function askQuestion(page: Page, text: string) {
  await page.getByLabel(chatShellCopy.inputAriaLabel).fill(text);
  await page.getByRole("button", { name: chatShellCopy.sendLabel }).click();
}

function buildSseStream(
  events: readonly [event: string, data: Record<string, unknown>][],
): string {
  return [
    ...events.flatMap(([event, data]) => [
      `event: ${event}`,
      `data: ${JSON.stringify(data)}`,
      "",
    ]),
    "",
  ].join("\n");
}
