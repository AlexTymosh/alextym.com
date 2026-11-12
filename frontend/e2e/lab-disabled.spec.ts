import { expect, test } from "@playwright/test";

test.describe("Portfolio Lab feature gate", () => {
  test.skip(
    process.env.PORTFOLIO_LAB_ENABLED === "true",
    "Disabled-mode regression is not applicable while Lab is explicitly enabled",
  );

  test("does not expose protected UI or session when not enabled", async ({ page, request }) => {
    const lab = await page.goto("/lab");
    expect(lab?.status()).toBe(404);
    const signIn = await page.goto("/lab/login");
    expect(signIn?.status()).toBe(404);
    const session = await request.get("/lab/session");
    expect(session.status()).toBe(404);
    const backendBridge = await request.get("/lab/api/identity");
    expect(backendBridge.status()).toBe(404);
  });
});
