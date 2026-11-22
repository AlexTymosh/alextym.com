import { expect, test } from "@playwright/test";

test.describe("Portfolio Lab feature gate", () => {
  test.skip(
    process.env.PORTFOLIO_LAB_ENABLED === "true",
    "Disabled-mode regression is not applicable while Lab is explicitly enabled",
  );

  test("does not expose protected UI or session when not enabled", async ({ page, request }) => {
    for (const path of ["/sign-in", "/setting", "/settings", "/settings/profile", "/settings/connections", "/settings/access", "/auth/action"]) {
      expect((await page.goto(path))?.status(), path).toBe(404);
    }
    for (const path of ["/auth/session", "/auth/identity", "/auth/profile"]) {
      expect((await request.get(path)).status(), path).toBe(404);
    }
    for (const path of ["/auth/session", "/auth/session/link", "/auth/session/reauthenticate", "/auth/access/grants", "/auth/password/reset", "/auth/profile"]) {
      expect((await request.post(path, { data: {} })).status(), path).toBe(404);
    }
  });
});
