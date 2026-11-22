import { expect, test } from "@playwright/test";

const site = "http://localhost:14300";
const project = "demo-portfolio-lab";
const emulator = "http://127.0.0.1:19099";
const enabled = process.env.LAB_EMULATOR_E2E === "true" &&
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID === project && process.env.PLAYWRIGHT_BASE_URL === site;

for (const [name, path] of [
  ["Fleet", "/portfolio/fleet-vor-hub"],
  ["Workforce", "/portfolio/workforce-intelligence"],
] as const) {
  test(`${name} has an accessible demo bar and returns to Portfolio without logging out`, async ({ page }, info) => {
    test.skip(!enabled, "Requires the isolated local Firebase emulator environment");
    test.setTimeout(60_000);
    const login = await page.request.post(emulator + "/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + project, {
      data: { email: "lab-preview@example.test", password: "LocalLabPreview-123!", returnSecureToken: true },
    });
    expect(login.ok()).toBeTruthy();
    const { idToken } = await login.json();
    expect((await page.request.post(site + "/auth/session", {
      headers: { Origin: site }, data: { idToken },
    })).status()).toBe(200);
    await page.goto(path);
    const bar = page.getByRole("navigation", { name: "Demo navigation", exact: true });
    await expect(bar).toBeVisible();
    await expect(bar).toContainText("Demo v1.0 · Synthetic data only");
    await expect(bar).toHaveCSS("background-color", "rgb(7, 7, 7)");
    const back = bar.getByRole("link", { name: "Back to portfolio" });
    await expect(back).toHaveAttribute("href", "/portfolio");
    await back.focus();
    await expect(back).toBeFocused();
    await expect(back).toHaveCSS("outline-style", "solid");
    await expect(page.getByRole("button", { name: "Log Out", exact: true })).toBeVisible();
    const bannerBounds = await bar.boundingBox();
    const buttonBounds = await page.getByRole("button", { name: "Log Out", exact: true }).boundingBox();
    expect(bannerBounds!.y).toBe(0);
    expect(buttonBounds!.y).toBeGreaterThanOrEqual(bannerBounds!.height);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    if (name === "Workforce") {
      await expect(page.getByText("Prepared for an SCAS interview", { exact: false })).toHaveCount(0);
      await page.getByRole("button", { name: "Switch to light theme", exact: true }).click();
      await expect(page.getByRole("region", { name: "Workforce Intelligence demo" })).toHaveAttribute("data-theme", "light");
      await expect(bar).toHaveCSS("background-color", "rgb(7, 7, 7)");
      await page.getByRole("navigation", { name: "Workforce sections" }).getByRole("link", { name: "People Voice", exact: true }).click();
      await expect(bar).toBeVisible();
    }
    await bar.screenshot({ path: info.outputPath("demo-bar.png") });
    await back.click();
    await expect(page).toHaveURL(site + "/portfolio");
    await expect(page.getByRole("heading", { name: "Portfolio", exact: true })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Demo navigation", exact: true })).toHaveCount(0);
    expect((await page.request.get("/auth/session")).status()).toBe(200);
  });
}
