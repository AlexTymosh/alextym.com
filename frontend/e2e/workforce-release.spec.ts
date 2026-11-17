import { expect, test, type Page } from "@playwright/test";
import { setTimeout } from "node:timers/promises";

const path = "/portfolio/workforce-intelligence";
const origin = "http://127.0.0.1:14300";
const password = process.env.WORKFORCE_E2E_PASSWORD;
const passwordDemo = process.env.WORKFORCE_PASSWORD_E2E === "true" &&
  process.env.PLAYWRIGHT_BASE_URL === origin && !!password;

async function enterDemo(page: Page, suffix = "") {
  await page.goto(path + suffix);
  await page.getByLabel("Demo password").fill(password!);
  await page.getByRole("button", { name: "Enter demo" }).click();
  await expect(page.getByRole("navigation", { name: "Workforce sections" })).toBeVisible();
}

test("planning separates actuals and predictions and saves a revision-pinned comparison", async ({ page }, info) => {
  test.skip(!passwordDemo || info.project.name !== "chromium", "Requires a disposable local password demo");
  test.setTimeout(100_000);
  await enterDemo(page);
  const planning = page.getByRole("navigation", { name: "Workforce Intelligence outline" }).getByRole("group", { name: "Planning & insight" });

  const forecast = page.locator("#forecast");
  await planning.getByRole("link", { name: "Forecasting" }).click();
  await forecast.getByLabel("Enable forecast").check();
  await expect(forecast.getByRole("status")).toContainText("Insufficient history");
  await expect(forecast.getByRole("img")).toHaveAttribute("aria-label", /Monthly actuals/);

  await page.getByRole("button", { name: "Load full dataset" }).click();
  async function confirmFull() {
    const request = page.waitForResponse((response) => response.url().endsWith("/api/demo/seed") &&
      response.request().method() === "POST");
    await page.getByRole("button", { name: "Confirm dataset replacement" }).click();
    return request;
  }
  let replacement = await confirmFull();
  if (replacement.status() === 429) {
    const retryAfter = Number(replacement.headers()["retry-after"]);
    expect(retryAfter).toBeGreaterThan(0);
    expect(retryAfter).toBeLessThanOrEqual(15);
    await setTimeout(retryAfter * 1_000);
    replacement = await confirmFull();
  }
  expect(replacement.ok()).toBe(true);
  await expect(page.getByText("Full synthetic dataset is ready.")).toBeVisible({ timeout: 20_000 });
  await forecast.getByLabel("Enable forecast").check();
  await expect(forecast.getByRole("status")).toContainText("One-month-ahead mean absolute error");
  await expect(forecast.getByRole("img")).toHaveAttribute("aria-label", /Actuals through 2026-10. Forecast starts 2026-11/);
  await forecast.getByText("Monthly values", { exact: true }).click();
  await expect(forecast.getByRole("row").filter({ hasText: "2026-11" })).toContainText("Forecast");
  await forecast.getByLabel("Enable forecast").uncheck();
  await expect(forecast.getByRole("img")).toHaveAttribute("aria-label", /Monthly actuals/);

  const scenario = page.locator("#scenarios");
  await planning.getByRole("link", { name: "What-if scenarios" }).click();
  await expect(forecast).toHaveCount(0);
  await scenario.getByLabel("Offer acceptance (%)").fill("0");
  const saved = page.waitForResponse((response) => response.url().endsWith("/api/scenarios") &&
    response.request().method() === "POST");
  await scenario.getByRole("button", { name: "Run scenario" }).click();
  const result = await saved;
  expect(result.ok()).toBe(true);
  const { run_id: id, evaluation } = await result.json();
  expect(evaluation.scenario.expected_starts).toBe(0);
  expect(evaluation.baseline.expected_starts).toBeGreaterThan(0);
  await expect(scenario.getByRole("heading", { name: "Scenario comparison" })).toBeVisible();
  await expect(scenario.getByRole("columnheader", { name: "Reference baseline" })).toBeVisible();
  const read = await page.request.get(`${path}/api/scenarios/${id}`);
  expect(read.status()).toBe(200);
  expect(read.headers()["cache-control"]).toBe("no-store");
  const crossOrigin = await page.request.post(`${path}/api/scenarios`, {
    headers: { Origin: "https://outside.example" }, data: {},
  });
  expect(crossOrigin.status()).toBe(403);
});

test("ten-minute guide and process remain navigable on a narrow screen", async ({ page }, info) => {
  test.skip(!passwordDemo || info.project.name !== "chromium", "Requires a disposable local password demo");
  test.setTimeout(75_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await enterDemo(page, "?mode=workforce-management&scenario=full&step=workbook");
  const guide = page.getByRole("complementary", { name: "Active interview guide" });
  await expect(guide).toContainText("Ten-minute walkthrough");
  await expect(page.locator("#import-export")).toBeVisible();
  await guide.getByRole("button", { name: "Next step" }).click();
  await expect(page.locator("#scenarios")).toBeVisible();
  await guide.getByRole("button", { name: "Next step" }).click();
  await expect(page.locator("#voice-review")).toBeVisible();
  await guide.getByRole("button", { name: "Next step" }).click();
  await expect(page).toHaveURL(/scenario=full&step=action$/);
  await guide.getByRole("button", { name: "Next step" }).click();

  const process = page.locator("#voice-process");
  await expect(process.getByRole("heading", { level: 2 })).toHaveText("People Voice to Action");
  await process.getByLabel("Diagram zoom").selectOption("125");
  await process.getByRole("button", { name: "Next activity" }).focus();
  await page.keyboard.press("Enter");
  await expect(process.locator("#process-activity")).toContainText("Create survey");
  await process.getByRole("button", { name: "Show exceptions for Structured evidence valid?" }).click();
  await expect(process.locator("#process-activity")).toContainText("Unsupported evidence");
  await expect(process.locator("#process-activity")).toContainText("Invalid JSON");

  await guide.getByRole("button", { name: "Next step" }).click();
  await expect(page.locator("#audit-history")).toBeVisible();
  await guide.getByRole("button", { name: "Next step" }).click();
  await expect(page.getByRole("heading", { name: "Data quality checks" })).toBeVisible();
  const section = page.getByRole("combobox", { name: "Section", exact: true });
  await expect(section).toHaveValue("quality");
  await section.selectOption("data-layers");
  await expect(page.locator("#quality")).toHaveCount(0);
  const layers = page.locator("#data-layers");
  await layers.getByRole("button", { name: "Gold", exact: true }).click();
  await expect(layers.getByRole("region", { name: "Gold example row" })).toContainText("workforce_gap_wte");
  await page.reload();
  await expect(layers).toBeVisible();
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  const app = page.getByRole("region", { name: "Workforce Intelligence demo" });
  await expect(app).toHaveAttribute("data-theme", "light");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
