import { expect, test, type Page } from "@playwright/test";

const path = "/portfolio/workforce-intelligence";
const localOrigin = "http://127.0.0.1:14300";
const useEmulators = process.env.WORKFORCE_MVP_E2E === "true" && process.env.PLAYWRIGHT_BASE_URL === localOrigin;

async function signIn(page: Page) {
  await page.goto("/lab/login");
  await page.getByLabel("Email", { exact: true }).fill("workforce-member@example.test");
  await page.getByLabel("Password", { exact: true }).fill("Workforce-emulator-only-091!");
  await page.getByRole("button", { name: "Sign in with email" }).click();
  await expect(page).toHaveURL(/\/lab$/, { timeout: 20_000 });
}

test("an admitted Workforce member can save effective FTE and see Gold refresh", async ({ page }, info) => {
  test.skip(!useEmulators || info.project.name !== "chromium", "Requires the disposable local Firebase and SQLite fixtures");
  test.setTimeout(90_000);
  await signIn(page);
  await page.goto(path);
  await expect(page.getByRole("heading", { name: "Recruitment overview" })).toBeVisible({ timeout: 20_000 });
  const workspaceNav = page.getByRole("navigation", { name: "Workforce sections" });
  const gap = page.locator("[data-metric=workforce_gap_wte]");
  const prior = Number((await gap.innerText()).split(" ")[0]);
  await page.evaluate(() => { document.documentElement.dataset.workforceApp = "running"; });

  await workspaceNav.getByRole("link", { name: "Workforce Management" }).click();
  await page.getByRole("button", { name: "Edit FTE for Demo A.", exact: true }).click({ timeout: 20_000 });
  const field = page.getByLabel("New contracted FTE");
  const oldFte = Number(await field.inputValue());
  const newFte = oldFte === 1 ? 0.8 : 1;
  await field.fill(String(newFte));
  const saved = page.waitForResponse((res) => res.url().includes("/api/employees/emp-001/contracts") &&
    res.request().method() === "PATCH");
  await page.getByRole("button", { name: "Save FTE" }).click();
  expect((await saved).status()).toBe(200);
  await expect(page.getByRole("status").filter({ hasText: "Demo A. contract saved" })).toBeVisible();

  await workspaceNav.getByRole("link", { name: "Workforce Intelligence" }).click();
  await expect(gap).toHaveText(`${Number((prior + oldFte - newFte).toFixed(3))} WTE`);
  expect(await page.evaluate(() => document.documentElement.dataset.workforceApp)).toBe("running");
  await page.getByLabel("Definition of Workforce gap").click();
  await expect(page.getByText("Budgeted establishment WTE − substantive WTE", { exact: true })).toBeVisible();

  await page.reload();
  await expect(gap).toHaveText(`${Number((prior + oldFte - newFte).toFixed(3))} WTE`);
  await page.getByLabel("Period start").fill("2026-07-01");
  await page.getByLabel("As of date").fill("2026-07-30");
  await page.getByRole("button", { name: "Apply dates" }).click();
  await expect(page.getByText("There are no applications in this cohort.")).toBeVisible();
  await expect(page.locator("[data-metric=offer_acceptance_rate]")).toHaveText("Not available");
});

test("a member can inspect published evidence, a governed answer and the implemented lineage", async ({ page }, info) => {
  test.skip(!useEmulators || info.project.name !== "chromium", "Requires the disposable local Firebase and SQLite fixtures");
  test.setTimeout(60_000);
  await signIn(page);
  await page.goto(path);
  const nav = page.getByRole("navigation", { name: "Workforce sections" });
  const rate = await page.locator("[data-metric=vacancy_rate]").innerText();
  await page.getByRole("button", { name: "Explain the vacancy rate" }).click();
  const answer = page.locator("#insight-pilot").getByRole("status");
  await expect(answer).toContainText(rate);
  await expect(answer).toContainText("Open vacancy WTE ÷ budgeted establishment WTE × 100");

  await nav.getByRole("link", { name: "People Voice" }).click();
  await expect(page.getByRole("heading", { name: "Rota Changes and Workforce Pressure" })).toBeVisible();
  await expect(page.getByText("Demonstration fallback result")).toBeVisible();
  const findings = page.getByRole("region", { name: "Published findings" });
  await expect(findings.getByText("6 of 10 comments")).toBeVisible();
  await expect(findings.getByText("Seeded demonstration review")).toBeVisible();
  await findings.getByRole("link", { name: "rota-001" }).click();
  await expect(page).toHaveURL(/#response-rota-001$/);
  await expect(findings.locator("#response-rota-001")).toContainText("Give the team a little more notice");
  await expect(page.getByRole("heading", { name: "Linked management action" })).toBeVisible();

  await nav.getByRole("link", { name: "Data Architecture" }).click();
  await expect(page.getByRole("heading", { name: "From source records to reports" })).toBeVisible();
  await expect(page.getByText("Executive metrics · gold_reviewed_survey_findings")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Metric catalogue" })).toBeVisible();
});
