import { expect, test } from "@playwright/test";

const routes = [
  "/fleet-vor-hub/register",
  "/fleet-vor-hub/new-defect",
  "/fleet-vor-hub/process",
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
  const response = await page.goto("/fleet-vor-hub");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Fleet VOR Hub" })).toBeVisible();
  await expect(page.getByLabel("Demo password")).toBeVisible();
});

for (const oldRoute of routes) {
  test(`${oldRoute} still redirects to the Fleet Hub`, async ({ page }) => {
    await page.goto(oldRoute);
    await expect(page).toHaveURL(/\/fleet-vor-hub\/?$/);
    await expect(page.getByRole("heading", { name: "Fleet VOR Hub" })).toBeVisible();
  });
}
