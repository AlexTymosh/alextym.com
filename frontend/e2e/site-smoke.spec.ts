import { expect, test } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await mockWarmup(page);
});

test("renders key public pages", async ({ page }) => {
  await gotoAndExpectOk(page, "/");
  await expect(
    page.getByRole("heading", { name: "Alex Tymoshenko" }),
  ).toBeVisible();

  await gotoAndExpectOk(page, "/resume");
  await expect(
    page.getByRole("heading", { name: "Alex Tymoshenko" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /download concise cv/i }),
  ).toBeVisible();

  await gotoAndExpectOk(page, "/chat");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Alex's AI Assistant",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: /ask alex/i }),
  ).toBeVisible();

  await gotoAndExpectOk(page, "/contact");
  await expect(
    page.getByRole("heading", { name: "Contact Me" }),
  ).toBeVisible();
  await expect(
    page.getByRole("form", { name: "Contact form" }),
  ).toBeVisible();
});

test("navigates between primary pages from the main navigation", async ({
  page,
}) => {
  await gotoAndExpectOk(page, "/");

  const navigation = page.getByRole("navigation", {
    name: "Main navigation",
  });

  await navigation.getByRole("link", { name: "Resume" }).click();
  await expect(page).toHaveURL(/\/resume$/);
  await expect(
    page.getByRole("heading", { name: "Alex Tymoshenko" }),
  ).toBeVisible();

  await navigation.getByRole("link", { name: "Chat" }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Alex's AI Assistant",
    }),
  ).toBeVisible();

  await navigation.getByRole("link", { name: "Contact" }).click();
  await expect(page).toHaveURL(/\/contact$/);
  await expect(
    page.getByRole("heading", { name: "Contact Me" }),
  ).toBeVisible();

  await navigation.getByRole("link", { name: "Home" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { name: "Alex Tymoshenko" }),
  ).toBeVisible();
});

test("renders the contact form without sending email", async ({ page }) => {
  await gotoAndExpectOk(page, "/contact");

  await expect(page.getByLabel("Your Name")).toBeVisible();
  await expect(page.getByLabel("Email Address")).toBeVisible();
  await expect(page.getByLabel("Message")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Send Message" }),
  ).toBeEnabled();
});

test("renders the chat shell without requiring the live backend", async ({
  page,
}) => {
  await gotoAndExpectOk(page, "/chat");

  const chatShell = page.getByLabel("AI digital assistant");

  await expect(chatShell.getByText("Ready", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Give me your 1-minute intro." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Give me a short overview of his work experience.",
    }),
  ).toBeVisible();
});

async function gotoAndExpectOk(page: Page, path: string): Promise<void> {
  const response = await page.goto(path);

  expect(response, `${path} should return an HTTP response`).not.toBeNull();
  expect(response?.status(), `${path} should not return an error`).toBeLessThan(
    400,
  );
}

async function mockWarmup(page: Page): Promise<void> {
  await page.route("**/api/warmup", async (route) => {
    await fulfillJson(route, { status: "warmed" });
  });
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
