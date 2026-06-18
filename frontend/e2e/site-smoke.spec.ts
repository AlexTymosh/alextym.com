import { expect, test } from "@playwright/test";
import type { Page, Route } from "@playwright/test";
import { chatShellCopy } from "../content/chat";
import {
  chatConfig,
  contactConfig,
  resumeConfig,
} from "../lib/project-config";

test.beforeEach(async ({ page }) => {
  await mockWarmup(page);
});

test("renders key public pages", async ({ page }) => {
  await gotoAndExpectOk(page, "/");
  await expect(
    page.getByRole("heading", { name: resumeConfig.pageHeading }),
  ).toBeVisible();

  await gotoAndExpectOk(page, "/resume");
  await expect(
    page.getByRole("heading", { name: resumeConfig.pageHeading }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /download concise cv/i }),
  ).toBeVisible();

  await gotoAndExpectOk(page, "/chat");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: chatShellCopy.title,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: chatShellCopy.inputAriaLabel }),
  ).toBeVisible();

  await gotoAndExpectOk(page, "/contact");
  await expect(
    page.getByRole("heading", { name: contactConfig.heading.title }),
  ).toBeVisible();
  await expect(
    page.getByRole("form", { name: contactConfig.form.ariaLabel }),
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
    page.getByRole("heading", { name: resumeConfig.pageHeading }),
  ).toBeVisible();

  await navigation.getByRole("link", { name: "Chat" }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: chatShellCopy.title,
    }),
  ).toBeVisible();

  await navigation.getByRole("link", { name: "Contact" }).click();
  await expect(page).toHaveURL(/\/contact$/);
  await expect(
    page.getByRole("heading", { name: contactConfig.heading.title }),
  ).toBeVisible();

  await navigation.getByRole("link", { name: "Home" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { name: resumeConfig.pageHeading }),
  ).toBeVisible();
});

test("renders the contact form without sending email", async ({ page }) => {
  await gotoAndExpectOk(page, "/contact");

  await expect(page.getByLabel(contactConfig.form.fields.name.label)).toBeVisible();
  await expect(page.getByLabel(contactConfig.form.fields.email.label)).toBeVisible();
  await expect(page.getByLabel(contactConfig.form.fields.message.label)).toBeVisible();
  await expect(
    page.getByRole("button", { name: contactConfig.form.submitLabel }),
  ).toBeEnabled();
});

test("renders the chat shell without requiring the live backend", async ({
  page,
}) => {
  await gotoAndExpectOk(page, "/chat");

  const chatShell = page.getByLabel(chatShellCopy.ariaLabel);

  await expect(
    chatShell.getByText(chatShellCopy.readyStatus, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: chatConfig.quickPrompts[0].label }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: chatConfig.quickPrompts[1].label,
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
