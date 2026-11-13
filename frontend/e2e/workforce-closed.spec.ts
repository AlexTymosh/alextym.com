import { expect, test } from "@playwright/test";

test.describe("Workforce project closed until shared RBAC release", () => {
  test("catalogue and project are not exposed before project RBAC exists", async ({ page }) => {
    const catalogue = await page.goto("/portfolio");
    expect(catalogue?.status()).toBe(404);
    const project = await page.goto("/portfolio/workforce-intelligence");
    expect(project?.status()).toBe(404);
    await expect(page.getByText("Project foundation only.")).toHaveCount(0);
  });
});
