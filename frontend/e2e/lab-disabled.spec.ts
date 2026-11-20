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
    const link = await request.post("/lab/session/link", { data: {} });
    expect(link.status()).toBe(404);
    const backendBridge = await request.get("/lab/api/identity");
    expect(backendBridge.status()).toBe(404);
    expect((await page.goto("/lab/admin"))?.status()).toBe(404);
    expect((await request.post("/lab/admin/grants", { data: {} })).status()).toBe(404);
    const passwordReset = await page.goto("/lab/password/reset");
    expect(passwordReset?.status()).toBe(404);
    const passwordAction = await request.post("/lab/password/reset/action", {
      data: { oobCode: "invalid", newPassword: "invalid" },
    });
    expect(passwordAction.status()).toBe(404);
    for (const path of ["/sign-in", "/settings", "/settings/profile", "/settings/connections", "/settings/access", "/auth/action"]) {
      expect((await page.goto(path))?.status(), path).toBe(404);
    }
    for (const path of ["/auth/session", "/auth/identity", "/auth/profile"]) {
      expect((await request.get(path)).status(), path).toBe(404);
    }
    for (const path of ["/auth/session", "/auth/session/link", "/auth/access/grants", "/auth/password/reset", "/auth/profile"]) {
      expect((await request.post(path, { data: {} })).status(), path).toBe(404);
    }
  });
});
