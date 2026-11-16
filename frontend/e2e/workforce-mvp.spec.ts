import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

const path = "/portfolio/workforce-intelligence";
const localOrigin = "http://127.0.0.1:14300";
const useEmulators = process.env.WORKFORCE_PASSWORD_E2E === "true" && !!process.env.WORKFORCE_E2E_PASSWORD && process.env.PLAYWRIGHT_BASE_URL === localOrigin;

async function signIn(page: Page) {
  await page.goto(path);
  await page.getByLabel("Demo password").fill(process.env.WORKFORCE_E2E_PASSWORD!);
  await page.getByRole("button", { name: "Enter demo" }).click();
  await expect(page.getByRole("heading", { name: "Recruitment overview" })).toBeVisible({ timeout: 20_000 });
}

test("a member previews a workbook before confirming source and dashboard changes", async ({ page }, info) => {
  const inputPath = process.env.WORKFORCE_OPS_XLSX_FILE;
  test.skip(!useEmulators || info.project.name !== "chromium" || !inputPath,
    "Requires local password-demo app and a synthetic workbook");
  test.setTimeout(60_000);
  const workbook = await readFile(inputPath!);
  const contentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  await signIn(page);
  await page.goto(`${path}?mode=workforce-management`);
  const outline = page.getByRole("navigation", { name: "Workforce Management outline" });
  await outline.getByRole("link", { name: "Import / Export" }).click();
  const importPanel = page.locator("#import-export");
  const template = page.waitForEvent("download");
  await importPanel.getByRole("button", { name: "Download template" }).click();
  expect((await template).suggestedFilename()).toBe("workforce-template.xlsx");
  await expect.poll(async () => (await page.request.post(`${path}/api/import/validate`, {
    headers: { origin: "https://untrusted.example", "content-type": contentType }, data: workbook,
  })).status()).toBe(403);
  await importPanel.getByLabel("Excel workbook", { exact: true }).setInputFiles({
    name: "synthetic-browser-import.xlsx", mimeType: contentType, buffer: workbook,
  });
  await importPanel.getByRole("button", { name: "Validate workbook" }).click();
  await expect(importPanel.getByRole("heading", { name: "Import preview" })).toBeVisible();
  await expect(importPanel.getByRole("status")).toContainText("1 to insert");
  const employeePath = `${path}/api/employees/browser-excel`;
  expect((await page.request.get(employeePath)).status()).toBe(404);
  await expect(importPanel.getByRole("button", { name: "Confirm import" })).toBeDisabled();
  const forecast = importPanel.getByRole("region", { name: "Dashboard impact" })
    .getByRole("row").filter({ hasText: "Current substantive workforce" });
  const projectedWte = await forecast.getByRole("cell").last().innerText();
  await importPanel.getByLabel("Apply these changes to the shared demo").check();
  await importPanel.getByRole("button", { name: "Confirm import" }).click();
  await expect(importPanel.getByRole("heading", { name: "Import receipt" })).toBeVisible();
  expect((await page.request.get(employeePath)).status()).toBe(200);
  await page.getByRole("navigation", { name: "Workforce sections" }).getByRole("link", { name: "Workforce Intelligence" }).click();
  await expect(page.locator("[data-metric=substantive_wte]")).toHaveText(`${projectedWte} WTE`);
});

test("an admitted Workforce member can save effective FTE and see Gold refresh", async ({ page }, info) => {
  test.skip(!useEmulators || info.project.name !== "chromium", "Requires the disposable local password-demo and SQLite fixtures");
  test.setTimeout(90_000);
  await signIn(page);
  await page.goto(path);
  await expect(page.getByRole("heading", { name: "Recruitment overview" })).toBeVisible({ timeout: 20_000 });
  const workspaceNav = page.getByRole("navigation", { name: "Workforce sections" });
  await expect(page.getByRole("heading", { name: "Recruitment channels" })).toBeVisible();
  const channels = page.getByRole("region", { name: "Recruitment channel table" });
  await expect(channels).toBeVisible();
  const ageing = page.getByRole("region", { name: "Vacancy ageing bands" });
  await expect(ageing).toBeVisible();
  await expect(ageing.getByRole("row")).toHaveCount(6); // Five bands plus header.
  await page.getByRole("button", { name: "View funnel for vac-004" }).click();
  const vacancy = page.getByRole("combobox", { name: "Vacancy", exact: true });
  await expect(vacancy).toHaveValue("vac-004");
  await vacancy.selectOption("");
  const trend = page.getByRole("region", { name: "Monthly Workforce trend table" });
  await expect(trend).toBeVisible();
  await expect(trend.getByRole("row")).toHaveCount(5); // 4 observed months plus header.
  await expect(trend.getByRole("row", { name: /2026-10/ })).toBeVisible();
  const inclusive = page.getByRole("region", { name: "Inclusive recruitment", exact: true });
  await expect(inclusive).toBeVisible();
  await expect(inclusive.getByRole("heading", { name: "Age band" })).toBeVisible();
  await expect(inclusive.getByRole("heading", { name: "Ethnicity group" })).toBeVisible();
  await expect(inclusive.getByRole("heading", { name: "Disability status" })).toBeVisible();
  await expect(inclusive.getByText("This disclosure-controlled report is independent", { exact: false })).toBeVisible();
  const withheld = await page.request.get(`${path}/api/analytics/inclusive-recruitment?as_of_date=2026-10-31`);
  expect(withheld.status()).toBe(404); // BFF blocks attempts to filter sensitive dimensions.
  const outcomes = page.getByRole("region", { name: "Workforce outcomes" });
  await expect(outcomes).toBeVisible();
  await expect(outcomes.locator("[data-metric=offer_to_start_conversion]")).toBeVisible();
  await expect(outcomes.locator("[data-metric=retention_rate]")).toBeVisible();
  await expect(outcomes.locator("[data-metric=early_attrition_12m]")).toHaveText("Not available");
  await expect(channels.getByRole("row").filter({ hasText: "Careers" })).toBeVisible();
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
  await expect(page.getByText("There are no applications in this reporting window.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Workforce outcomes" })).toBeVisible();
  const partialMonth = page.getByRole("region", { name: "Monthly Workforce trend table" });
  await expect(partialMonth.getByRole("row", { name: /2026-07 \(partial\)/ })).toBeVisible();
  await expect(page.locator("[data-metric=offer_acceptance_rate]")).toHaveText("Not available");
});

test("a member can inspect published evidence, a governed answer and the implemented lineage", async ({ page }, info) => {
  test.skip(!useEmulators || info.project.name !== "chromium", "Requires the disposable local password-demo and SQLite fixtures");
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 1080 });
  await signIn(page);
  await page.goto(path);
  const nav = page.getByRole("navigation", { name: "Workforce sections" });
  const rate = await page.locator("[data-metric=vacancy_rate]").innerText();
  await page.screenshot({ path: info.outputPath("workforce-recruitment.png"), style: "nextjs-portal { display: none }" });
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
  await page.screenshot({ path: info.outputPath("workforce-people-voice.png"), style: "nextjs-portal { display: none }" });
  await findings.getByRole("link", { name: "rota-001" }).click();
  await expect(page).toHaveURL(/#response-rota-001$/);
  await expect(findings.locator("#response-rota-001")).toContainText("Give the team a little more notice");
  await expect(page.getByRole("heading", { name: "Linked management action" })).toBeVisible();

  await nav.getByRole("link", { name: "Data Architecture" }).click();
  await expect(page.getByRole("heading", { name: "From source records to reports" })).toBeVisible();
  await expect(page.getByText("Executive metrics · gold_reviewed_survey_findings")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Metric catalogue" })).toBeVisible();
  const qualityDetails = page.getByRole("region", { name: "Data quality rule details" });
  await expect(qualityDetails.getByRole("row", { name: /Excluded applications/ })).toBeVisible();
  await expect(page.getByText("These are four source-to-Silver reconciliation checks", { exact: false })).toBeVisible();
  const register = page.getByRole("region", { name: "Sources and assumptions" });
  await expect(register.getByText("Synthetic recruitment events")).toBeVisible();
  await expect(register.getByText("SCAS People Strategy 2023–2026 · Public reference", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.getByRole("region", { name: "Workforce Intelligence demo" })).toHaveAttribute("data-theme", "light");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("reset is confirmed and the interview guides restore their real views", async ({ page }, info) => {
  test.skip(!useEmulators || info.project.name !== "chromium", "Requires the disposable local password-demo and SQLite fixtures");
  test.setTimeout(90_000);
  await signIn(page);
  await page.goto(path);
  const gap = page.locator("[data-metric=workforce_gap_wte]");
  await expect(gap).toBeVisible({ timeout: 20_000 });
  const stale = await page.context().newPage();
  await stale.goto(path);
  await expect(stale.locator("[data-metric=workforce_gap_wte]")).toBeVisible();
  await page.bringToFront();

  await page.getByRole("button", { name: "Reset demo" }).click();
  const confirm = page.getByRole("dialog", { name: "Reset the shared Workforce demo?" });
  await expect(confirm).toContainText("for every Workforce member");
  await confirm.getByRole("button", { name: "Cancel" }).click();
  await expect(confirm).not.toBeVisible();
  await page.getByRole("button", { name: "Reset demo" }).click();
  await confirm.getByRole("button", { name: "Confirm reset" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Demo reset." })).toBeVisible();
  const baselineGap = Number((await gap.innerText()).split(" ")[0]);
  await stale.bringToFront();
  await stale.getByRole("button", { name: "Refresh data" }).click();
  await expect(stale.getByText("The demo dataset was reset or regenerated.", { exact: false })).toBeVisible();
  await stale.close();
  await page.bringToFront();

  const guide = page.getByRole("complementary", { name: "Active interview guide" });
  await page.getByRole("button", { name: "Run interview scenario" }).click();
  await expect(guide).toContainText("90-second walkthrough");
  await guide.getByRole("button", { name: "Next step" }).click();
  await expect(page).toHaveURL(/scenario=quick&step=edit-fte$/);
  await page.reload();
  await expect(page.getByLabel("Effective date")).toHaveValue("2026-10-20");
  await page.getByLabel("New contracted FTE").fill("0.8");
  await page.getByRole("button", { name: "Save FTE" }).click();
  await expect(page.getByText("Demo A. contract saved", { exact: false })).toBeVisible();
  await guide.getByRole("button", { name: "Next step" }).click();
  await expect(gap).toHaveText(`${Number((baselineGap + 0.2).toFixed(3))} WTE`);
  await guide.getByRole("button", { name: "Next step" }).click();
  await page.getByRole("button", { name: "Explain the vacancy rate" }).click();
  await expect(page.locator("#insight-pilot").getByRole("status")).toContainText("14.29%");
  await guide.getByRole("button", { name: "Finish walkthrough" }).click();

  await page.getByLabel("Guided demo").selectOption("extended");
  await page.getByRole("button", { name: "Run interview scenario" }).click();
  for (const step of ["edit-fte", "updated-gap", "funnel", "voice-report", "evidence", "definition", "explain-rate", "lineage"]) {
    await guide.getByRole("button", { name: "Next step" }).click();
    await expect(page).toHaveURL(new RegExp(`scenario=extended&step=${step}$`));
    if (step === "funnel") await expect(page.getByRole("heading", { name: "Candidate funnel" })).toBeVisible();
    if (step === "evidence") await expect(page.getByRole("link", { name: "rota-001" })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "From source records to reports" })).toBeVisible();
  await guide.getByRole("button", { name: "Finish walkthrough" }).click();
  await expect(guide).toHaveCount(0);
});

test("sign-out clears the Workforce cookie and rejects BFF and direct Render data", async ({ page }, info) => {
  test.skip(!useEmulators || info.project.name !== "chromium", "Requires local password-demo environment");
  await signIn(page);
  const direct = "http://127.0.0.1:14800/api/workforce/demo/status";
  const bff = `${path}/api/demo/status`;
  const cookie = (await page.context().cookies()).find((item) => item.name === "workforce_demo_session");
  expect(cookie?.httpOnly).toBe(true);
  expect((await page.request.get(direct)).status()).toBe(401);
  expect((await page.request.get(bff)).status()).toBe(200);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Demo password")).toBeVisible();
  expect((await page.request.get(bff)).status()).toBe(401);
});
