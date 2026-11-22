import { expect, test } from "@playwright/test";
import { projectConfig } from "../lib/project-config";

const fleetPath = "/portfolio/fleet-vor-hub";
const routes = [
  "/fleet-vor-hub",
  "/fleet-vor-hub/register",
  "/fleet-vor-hub/new-defect",
  "/fleet-vor-hub/process",
  `${fleetPath}/register`,
  `${fleetPath}/new-defect`,
  `${fleetPath}/process`,
];

test.beforeEach(async ({ page }) => {
  await page.route("**/api/vor/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: true, authenticated: false, liveEmail: false }),
    });
  });
});

test("embedded Fleet Hub renders its access screen without a live API", async ({ page }) => {
  const response = await page.goto(fleetPath);
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Fleet VOR Hub" })).toBeVisible();
  await expect(page.getByLabel("Demo password")).toBeVisible();
});

for (const oldRoute of routes) {
  test(`${oldRoute} redirects permanently to the canonical Fleet Hub`, async ({ page, request }) => {
    const redirect = await request.get(oldRoute, { maxRedirects: 0 });
    expect(redirect.status()).toBe(308);
    expect(redirect.headers().location).toBe(fleetPath);
    await page.goto(oldRoute);
    await expect(page).toHaveURL(new RegExp(`${fleetPath}/?$`));
    await expect(page.getByRole("heading", { name: "Fleet VOR Hub" })).toBeVisible();
  });
}


test("Fleet demo remains noindex and website navigation survives returning home", async ({ page }) => {
  await page.goto(fleetPath);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `${projectConfig.site.canonicalUrl}${fleetPath}`);
  await expect(page.getByRole("heading", { name: "Fleet VOR Hub" })).toBeVisible();

  // The shared host shell remains mounted; Fleet visually owns the workspace.
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toHaveCount(1);
  const portfolio = page.getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Portfolio", exact: true });
  await expect(portfolio).toHaveAttribute("href", "/portfolio");
  await expect(portfolio).toHaveAttribute("aria-current", "location");
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Home", exact: true })).toBeVisible();
  await expect(portfolio).not.toHaveAttribute("aria-current", /.+/);
});

test("the canonical Fleet route retains its server-side project access gate", async ({ request }) => {
  test.skip(process.env.PORTFOLIO_LAB_ENABLED !== "true", "Requires the existing Firebase access mode");
  const legacy = await request.get("/fleet-vor-hub", { maxRedirects: 0 });
  expect(legacy.status()).toBe(308);
  expect(legacy.headers().location).toBe(fleetPath);
  const canonical = await request.get(fleetPath, { maxRedirects: 0 });
  expect(canonical.status()).toBe(307);
  expect(canonical.headers().location).toBe("/sign-in");
  expect((await request.get("/api/vor/bootstrap")).status()).toBe(401);
});
