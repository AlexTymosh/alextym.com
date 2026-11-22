import { expect, test } from "@playwright/test";

test("portfolio and navigation update the logged-in account together", async ({ page }) => {
  let requests = 0;
  let authenticated = true;
  await page.route("**/auth/profile", async (route) => {
    requests++;
    await route.fulfill({ status: authenticated ? 200 : 401, contentType: "application/json",
      body: JSON.stringify(authenticated ? { displayName: "reviewer@example.test", avatarUrl: null } : {}) });
  });
  await page.goto("/portfolio");
  const notice = page.getByRole("complementary", { name: "Demo access" });
  await expect(notice.getByRole("link", { name: "View your projects", exact: true })).toHaveAttribute("href", "/settings");
  await expect(page.locator(".nav-account")).toContainText("reviewer@example.test");
  await expect(page.getByRole("link", { name: "Log In", exact: true })).toHaveCount(0);
  const initialRequests = requests;
  authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event("account-profile-updated")));
  await expect(notice.getByRole("link", { name: "Log In", exact: true })).toHaveAttribute("href", "/sign-in");
  await expect(page.locator(".nav-account")).toHaveText("Log In");
  expect(requests).toBe(initialRequests + 1);
});

for (const status of [401, 503]) {
  test(`portfolio account response ${status} preserves the public catalogue`, async ({ page }) => {
    await page.route("**/auth/profile", (route) => route.fulfill({ status,
      contentType: "application/json", body: "{}" }));
    await page.goto("/portfolio");
    const notice = page.getByRole("complementary", { name: "Demo access" });
    await expect(notice.getByRole("link", { name: status === 401 ? "Log In" : "Settings", exact: true }))
      .toHaveAttribute("href", status === 401 ? "/sign-in" : "/settings");
    await expect(page.getByRole("heading", { name: "Fleet VOR Hub", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workforce & Recruitment Intelligence", exact: true })).toBeVisible();
  });
}
