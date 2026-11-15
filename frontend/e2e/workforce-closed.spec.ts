import { expect, test } from "@playwright/test";

test.describe("Workforce project default-off gate", () => {
  test.skip(
    process.env.WORKFORCE_INTELLIGENCE_ENABLED === "true",
    "Disabled-mode regression is not applicable while Workforce is explicitly enabled",
  );

  test("catalogue, app and BFF remain inaccessible by default", async ({ page, request }) => {
    const catalogue = await page.goto("/portfolio");
    expect(catalogue?.status()).toBe(404);
    const project = await page.goto("/portfolio/workforce-intelligence");
    expect(project?.status()).toBe(404);
    const proxy = await request.get("/portfolio/workforce-intelligence/api/status");
    expect(proxy.status()).toBe(404);
    await expect(page.getByText("Project foundation only.")).toHaveCount(0);
  });
});
