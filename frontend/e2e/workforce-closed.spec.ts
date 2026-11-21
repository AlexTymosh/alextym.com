import { expect, test } from "@playwright/test";

test.describe("Workforce project default-off gate", () => {
  test.skip(
    process.env.WORKFORCE_INTELLIGENCE_ENABLED === "true",
    "Disabled-mode regression is not applicable while Workforce is explicitly enabled",
  );

  test("the catalogue stays public while the Workforce app and API are disabled", async ({ page, request }) => {
    const catalogue = await page.goto("/portfolio");
    expect(catalogue?.status()).toBe(200);
    await expect(page.getByRole("link", { name: "Open Workforce & Recruitment Intelligence demo", exact: true }))
      .toHaveAttribute("href", "/portfolio/workforce-intelligence");
    const project = await page.goto("/portfolio/workforce-intelligence");
    expect(project?.status()).toBe(404);
    const proxy = await request.get("/portfolio/workforce-intelligence/api/status");
    expect(proxy.status()).toBe(404);
    await expect(page.getByText("Project foundation only.")).toHaveCount(0);
  });
});
