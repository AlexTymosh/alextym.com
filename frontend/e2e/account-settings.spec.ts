import { randomBytes } from "node:crypto";
import { test, expect, type Page } from "@playwright/test";
import sharp from "sharp";

const site = "http://localhost:14300";
const emulator = "http://127.0.0.1:19099";
const project = "demo-portfolio-lab";
const password = "Synthetic-account-password-123!";
const enabled = process.env.LAB_EMULATOR_E2E === "true" &&
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID === project && process.env.PLAYWRIGHT_BASE_URL === site;

async function register(page: Page) {
  const email = "account-" + randomBytes(8).toString("hex") + "@example.test";
  await page.goto("/sign-in");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account with email", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  return email;
}

test.describe("Site account settings", () => {
  test.skip(!enabled, "Requires the isolated local Firebase emulators");
  test.setTimeout(90_000);

  test("old account URLs return 404 without a redirect", async ({ request }) => {
    for (const path of ["/lab", "/lab/login", "/lab/admin", "/lab/password/reset", "/lab/session", "/lab/session/link", "/lab/api/identity", "/lab/admin/grants", "/lab/password/reset/action"]) {
      const response = await request.get(path, { maxRedirects: 0 });
      expect(response.status(), path).toBe(404);
      expect(response.headers()).not.toHaveProperty("location");
    }
    for (const path of ["/lab/session", "/lab/session/link", "/lab/admin/grants", "/lab/password/reset/action"]) {
      const response = await request.post(path, { data: {}, maxRedirects: 0 });
      expect(response.status(), path).toBe(404);
      expect(response.headers()).not.toHaveProperty("location");
    }
  });

  test("profile, avatar, project grants and navigation stay bound to the signed-in user", async ({ page, playwright }, info) => {
    const email = await register(page);
    await expect(page.locator(".nav-account")).toContainText(email);
    await expect(page).toHaveURL(site + "/settings");
    await expect(page.getByRole("status")).toContainText("No access has been assigned");
    const tabs = page.getByRole("navigation", { name: "Settings sections" });
    await tabs.getByRole("link", { name: "Profile", exact: true }).click();
    await page.getByLabel("First name", { exact: true }).fill("Taylor");
    await page.getByLabel("Last name", { exact: true }).fill("Example");
    const png = await sharp({ create: { width: 32, height: 32, channels: 3, background: "#ff3e00" } }).png().toBuffer();
    await page.getByLabel("Profile photo", { exact: true }).setInputFiles({ name: "avatar.png", mimeType: "image/png", buffer: png });
    await page.getByRole("button", { name: "Use photo", exact: true }).click();
    await page.getByRole("button", { name: "Save profile", exact: true }).click();
    await expect(page.getByRole("status")).toHaveText("Profile saved.");
    await expect(page.locator(".nav-account")).toContainText("Taylor Example");
    const profile = await (await page.request.get("/auth/profile")).json();
    expect(profile.avatarUrl).toMatch(/^data:image\/webp;base64,/);
    expect(profile.email).toBe(email);
    expect(profile).not.toHaveProperty("password");
    await page.reload();
    await expect(page.getByLabel("First name", { exact: true })).toHaveValue("Taylor");
    await expect(page.getByLabel("Last name", { exact: true })).toHaveValue("Example");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: info.outputPath("settings-profile.png"), fullPage: true });

    const change = { firstName: "Updated", lastName: "Example", avatarSource: "none", revision: profile.revision };
    const concurrent = await Promise.all([0, 1].map(() => page.request.post("/auth/profile", {
      headers: { Origin: site }, data: change,
    })));
    expect(concurrent.map((response) => response.status()).sort()).toEqual([200, 409]);
    expect((await page.request.post("/auth/profile", {
      headers: { Origin: "https://untrusted.example.test" }, data: { ...change, revision: profile.revision + 1 },
    })).status()).toBe(403);
    expect((await page.request.post("/auth/profile", {
      headers: { Origin: site }, data: { ...change, revision: profile.revision + 1, avatarSource: "upload",
        avatarData: "data:image/png;base64," + Buffer.from("<svg onload='alert(1)'/>").toString("base64") },
    })).status()).toBe(400);
    expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(403);
    expect((await page.request.get("/portfolio/workforce-intelligence/api/status")).status()).toBe(403);

    const guest = await playwright.request.newContext({ baseURL: site });
    try {
      expect((await guest.get("/auth/profile")).status()).toBe(401);
      expect((await guest.post("/auth/profile", { headers: { Origin: site }, data: change })).status()).toBe(401);
      const publicCatalogue = await guest.get("/portfolio");
      expect(publicCatalogue.status()).toBe(200);
      expect(await publicCatalogue.text()).toContain("Fleet VOR Hub");
    } finally { await guest.dispose(); }

    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page).toHaveURL(site + "/sign-in");
    await register(page);
    const other = await (await page.request.get("/auth/profile")).json();
    expect(other.firstName).toBe("");
    expect(other.displayName).toBe(other.email);
    expect(other.avatarUrl).toBeNull();
    expect(other.email).not.toBe(email);
  });

  test("avatar cropping preserves proportions, respects framing and can be cancelled", async ({ page }, info) => {
    await register(page);
    await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Profile", exact: true }).click();
    const png = await sharp({ create: { width: 600, height: 200, channels: 3, background: "#0000ff" } }).composite([
      { input: Buffer.from('<svg width="600" height="200"><rect x="200" width="200" height="200" fill="red"/><rect x="400" width="200" height="200" fill="#00aa00"/><circle cx="500" cy="100" r="50" fill="white"/></svg>') },
    ]).png().toBuffer();
    const file = { name: "landscape.png", mimeType: "image/png", buffer: png };
    await page.getByLabel("Profile photo", { exact: true }).setInputFiles(file);
    await expect(page.getByRole("button", { name: "Save profile", exact: true })).toBeDisabled();
    await page.getByRole("button", { name: "Cancel crop", exact: true }).click();
    expect((await (await page.request.get("/auth/profile")).json()).avatarUrl).toBeNull();
    await page.getByLabel("Profile photo", { exact: true }).setInputFiles(file);
    const zoom = page.getByRole("slider", { name: "Photo zoom", exact: true });
    await zoom.focus(); await zoom.press("End"); await expect(zoom).toHaveValue("4");
    await zoom.press("Home"); await expect(zoom).toHaveValue("1");
    const horizontal = page.getByRole("slider", { name: "Horizontal position", exact: true });
    const previewImage = page.getByRole("img", { name: "Avatar crop preview", exact: true });
    await previewImage.evaluate((element) => element.scrollIntoView({ block: "center", behavior: "instant" }));
    const preview = await previewImage.boundingBox();
    const point = { x: preview!.x + preview!.width / 2, y: preview!.y + preview!.height / 2 };
    expect(await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.tagName, point)).toBe("CANVAS");
    if (info.project.name === "mobile-chrome") {
      const touch = await page.context().newCDPSession(page);
      await touch.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [point] });
      await touch.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ ...point, x: point.x - 40 }] });
      await touch.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      await touch.detach();
    } else {
      await page.mouse.move(point.x, point.y);
      await page.mouse.down();
      await page.mouse.move(point.x - 40, point.y, { steps: 4 });
      await page.mouse.up();
    }
    await expect.poll(async () => Number(await horizontal.inputValue())).toBeGreaterThan(50);
    await horizontal.focus(); await horizontal.press("End");
    await expect(horizontal).toHaveValue("100");
    await expect(page.getByRole("button", { name: "Use photo", exact: true })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: info.outputPath("avatar-cropper.png"), fullPage: true });
    await page.getByRole("button", { name: "Use photo", exact: true }).click();
    await page.getByRole("button", { name: "Save profile", exact: true }).click();
    await expect(page.getByRole("status")).toHaveText("Profile saved.");
    const cropped = (await (await page.request.get("/auth/profile")).json()).avatarUrl;
    const { data, info: pixels } = await sharp(Buffer.from(cropped.split(",")[1], "base64")).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    expect([pixels.width, pixels.height]).toEqual([256, 256]);
    const color = (x: number, y: number) => Array.from(data.subarray((y * pixels.width + x) * 4, (y * pixels.width + x) * 4 + 3));
    expect(color(16, 128)[1]).toBeGreaterThan(120);
    expect(color(16, 128)[0]).toBeLessThan(30);
    const white = (x: number, y: number) => color(x, y).every((channel) => channel > 220);
    const across = Array.from({ length: 256 }, (_, x) => white(x, 128)).filter(Boolean).length;
    const down = Array.from({ length: 256 }, (_, y) => white(128, y)).filter(Boolean).length;
    expect(across).toBeGreaterThan(120);
    expect(Math.abs(across - down)).toBeLessThanOrEqual(3);

    await page.getByRole("button", { name: "Adjust crop", exact: true }).click();
    await page.getByRole("button", { name: "Fit whole photo", exact: true }).click();
    await expect(page.getByRole("slider", { name: "Photo zoom", exact: true })).toBeDisabled();
    await page.getByRole("button", { name: "Use photo", exact: true }).click();
    await page.getByRole("button", { name: "Save profile", exact: true }).click();
    await expect(page.getByRole("status")).toHaveText("Profile saved.");
    const fitted = (await (await page.request.get("/auth/profile")).json()).avatarUrl;
    // Inspect the encoded result after trimming transparent margins.
    const fittedBounds = await sharp(Buffer.from(fitted.split(",")[1], "base64"))
      .trim({ background: "#00000000" }).toBuffer({ resolveWithObject: true });
    expect(fittedBounds.info.width / fittedBounds.info.height).toBeGreaterThan(2.9);
    expect(fittedBounds.info.width / fittedBounds.info.height).toBeLessThan(3.1);
  });

  test("Firebase reset links show the brand, confirm passwords and reject reuse", async ({ page }) => {
    const email = await register(page);
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByRole("button", { name: "Password help", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("Check your inbox");
    const codes = await (await page.request.get(emulator + "/emulator/v1/projects/" + project + "/oobCodes")).json();
    const code = codes.oobCodes.filter((entry: { email: string; requestType: string }) =>
      entry.email === email && entry.requestType === "PASSWORD_RESET").at(-1).oobCode;
    const link = "/auth/action?mode=resetPassword&oobCode=" + encodeURIComponent(code);
    await page.goto(link);
    await expect(page.getByLabel("New password", { exact: true })).toBeVisible();
    await expect(page.locator('img[src*="icon.png"]')).toBeVisible();
    await expect(page).toHaveURL(site + "/auth/action");
    await page.getByLabel("New password", { exact: true }).fill(password + "-new");
    await page.getByLabel("Confirm password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Set password", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("do not match");
    await page.getByLabel("Confirm password", { exact: true }).fill(password + "-new");
    await page.getByRole("button", { name: "Show password", exact: true }).first().click();
    await expect(page.getByLabel("New password", { exact: true })).toHaveAttribute("type", "text");
    await page.getByRole("button", { name: "Hide password", exact: true }).click();
    await page.getByRole("button", { name: "Set password", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Password updated", exact: true })).toBeVisible();
    await page.goto(link);
    await expect(page.getByRole("status")).toContainText("already been used");
    const old = await page.request.post(emulator + "/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + project, {
      data: { email, password, returnSecureToken: true },
    });
    expect(old.ok()).toBeFalsy();
    await page.goto("/sign-in");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password + "-new");
    await page.getByRole("button", { name: "Sign in with email", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  });
});
