import { randomBytes } from "node:crypto";
import { expect, test, type Page, type APIRequestContext } from "@playwright/test";

const emulator = "http://127.0.0.1:19099";
const site = "http://localhost:14300";
const backend = "http://127.0.0.1:14800";
const project = "demo-portfolio-lab";
const password = "Synthetic-preview-password-123!";
const enabled = process.env.LAB_EMULATOR_E2E === "true" &&
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID === project &&
  process.env.PLAYWRIGHT_BASE_URL === site;

async function mockProvider(page: Page, action: string, email: string) {
  await page.bringToFront();
  const button = page.getByRole("button", { name: action, exact: true });
  await button.waitFor({ timeout: 15_000 });
  const [popup] = await Promise.all([page.waitForEvent("popup", { timeout: 15_000 }), button.click()]);
  await popup.waitForURL(emulator + "/**");
  const account = popup.getByText(email, { exact: true });
  const input = popup.locator("#email-input");
  const add = popup.getByRole("button", { name: "Add new account" });
  await account.or(input).or(add).filter({ visible: true }).first().waitFor();
  const closed = popup.waitForEvent("close");
  if (await account.isVisible()) {
    await account.click();
  } else {
    if (await add.isVisible()) await add.click();
    await input.fill(email);
    await popup.locator("#sign-in").click();
  }
  await closed;
}

async function ownerSession(request: APIRequestContext) {
  const login = await request.post(emulator + "/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + project, {
    data: { email: "lab-preview@example.test", password: "LocalLabPreview-123!", returnSecureToken: true },
  });
  expect(login.ok()).toBeTruthy();
  const { idToken } = await login.json();
  const session = await request.post(site + "/auth/session", { headers: { Origin: site }, data: { idToken } });
  expect(session.status()).toBe(200);
}

async function findUserRow(page: Page, uid: string) {
  await page.goto("/settings/access");
  for (;;) {
    const row = page.locator(`tr[data-user-id="${uid}"]`);
    if (await row.count()) return row;
    const next = page.getByRole("link", { name: "Next accounts", exact: true });
    await expect(next).toBeVisible();
    const href = await next.getAttribute("href");
    await page.goto(href!);
  }
}

test.describe("Portfolio Lab self-service approval", () => {
  test.skip(!enabled, "Requires the isolated localhost Firebase emulator environment");
  test.setTimeout(90_000);

  test("linking after an old session and reload confirms the same account without logging out", async ({ page }) => {
    const email = `reauth-${randomBytes(6).toString("hex")}@example.test`;
    await page.goto("/sign-in");
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Create account with email", exact: true }).click();
    await page.getByRole("heading", { name: "Settings", exact: true }).waitFor();
    const cookie = (await page.context().cookies()).find((item) => item.name.endsWith("portfolio_lab_session"))!;
    // Unsigned emulator tokens let this isolated fixture age the website session.
    const parts = cookie.value.split(".");
    const claims = JSON.parse(Buffer.from(parts[1], "base64url").toString());
    claims.auth_time -= 3600;
    const agedUser = await page.request.post(emulator + "/identitytoolkit.googleapis.com/v1/projects/" + project + "/accounts:update", {
      headers: { Authorization: "Bearer owner" },
      data: { localId: claims.sub, validSince: String(claims.auth_time - 1) },
    });
    expect(agedUser.status()).toBe(200);
    parts[1] = Buffer.from(JSON.stringify(claims)).toString("base64url");
    await page.context().addCookies([{ ...cookie, value: parts.join(".") }]);
    await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Login methods", exact: true }).click();
    expect(await (await page.request.get("/auth/session")).json()).toMatchObject({
      authenticated: true, canLink: true,
    });
    const wrong = await page.request.post(emulator + "/identitytoolkit.googleapis.com/v1/accounts:signUp?key=" + project, {
      data: { email: "other-" + email, password, returnSecureToken: true },
    });
    const wrongToken = (await wrong.json()).idToken;
    expect((await page.request.post("/auth/session/reauthenticate", {
      headers: { Origin: site }, data: { idToken: wrongToken },
    })).status()).toBe(403);
    const login = await page.request.post(emulator + "/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + project, {
      data: { email, password, returnSecureToken: true },
    });
    const ownToken = (await login.json()).idToken;
    const unapproved = ownToken.split(".");
    const unapprovedClaims = JSON.parse(Buffer.from(unapproved[1], "base64url").toString());
    unapprovedClaims.firebase = { sign_in_provider: "google.com", identities: { "google.com": ["unapproved-subject"] } };
    unapproved[1] = Buffer.from(JSON.stringify(unapprovedClaims)).toString("base64url");
    expect((await page.request.post("/auth/session/reauthenticate", {
      headers: { Origin: site }, data: { idToken: unapproved.join(".") },
    })).status()).toBe(403);
    expect((await page.request.post("/auth/session/reauthenticate", {
      headers: { Origin: "https://untrusted.example.test" }, data: { idToken: ownToken },
    })).status()).toBe(403);
    for (const name of ["Google", "GitHub", "Facebook"].filter((name) =>
      name !== "GitHub" || process.env.NEXT_PUBLIC_FIREBASE_GITHUB_ENABLED === "true")) {
      await mockProvider(page, "Link " + name, name.toLowerCase() + "-" + email);
      await mockProvider(page, "Confirm " + name, name.toLowerCase() + "-" + email);
      await expect(page.getByRole("status")).toContainText(name + " is linked");
    }
    await page.reload();
    await page.getByRole("button", { name: "Link Microsoft", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Confirm your identity", exact: true })).toBeVisible();
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Confirm identity", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("Identity confirmed");
    await mockProvider(page, "Link Microsoft", "linked-" + email);
    await mockProvider(page, "Confirm Microsoft", "linked-" + email);
    await expect(page.getByRole("status")).toContainText("Microsoft is linked");
    expect((await (await page.request.get("/auth/profile")).json()).email).toBe(email);
  });

  test("email registration, Owner approval, project isolation and revocation", async ({ page, playwright }, testInfo) => {
    const email = `new-user-${randomBytes(6).toString("hex")}@example.test`;
    await page.goto("/sign-in");
    const emailButton = await page.getByRole("button", { name: "Log In with email", exact: true }).boundingBox();
    const microsoft = await page.getByRole("button", { name: "Continue with Microsoft", exact: true }).boundingBox();
    expect(emailButton!.y).toBeLessThan(microsoft!.y);
    await page.screenshot({ path: testInfo.outputPath("email-first-login.png"), fullPage: true, caret: "initial" });
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm password", { exact: true }).fill(password);
    const signup = page.waitForResponse((response) => response.url().includes("accounts:signUp"));
    await page.getByRole("button", { name: "Create account with email", exact: true }).click();
    const { localId: uid } = await (await signup).json();
    await page.getByRole("heading", { name: "Settings", exact: true }).waitFor();
    await expect(page.getByRole("status")).toContainText("No access has been assigned");
    await expect(page.getByRole("link", { name: "Open" })).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath("pending-access.png"), fullPage: true, caret: "initial" });
    expect((await page.request.get("/settings/access")).status()).toBe(404);
    expect((await page.request.post("/auth/access/grants", {
      headers: { Origin: site }, data: { uid, projectId: "fleet_hub", role: "Admin", revision: 0 },
    })).status()).toBe(403);
    expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(403);
    expect((await page.request.get("/portfolio/workforce-intelligence/api/status")).status()).toBe(403);

    const owner = await playwright.request.newContext();
    try {
      await ownerSession(owner);
      expect((await owner.get(site + "/settings/access")).status()).toBe(200);
      const change = { uid, projectId: "fleet_hub", role: "View", revision: 0 };
      const attempts = await Promise.all([0, 1].map(() => owner.post(site + "/auth/access/grants", {
        headers: { Origin: site }, data: change,
      })));
      expect(attempts.map((response) => response.status()).sort()).toEqual([200, 409]);
      expect((await owner.post(site + "/auth/access/grants", {
        headers: { Origin: "https://untrusted.example.test" }, data: change,
      })).status()).toBe(403);

      await page.reload();
      await expect(page.getByText("Fleet VOR Hub", { exact: true })).toBeVisible();
      await expect(page.getByText("View access", { exact: true })).toBeVisible();
      await expect(page.getByText("Workforce & Recruitment Intelligence", { exact: true })).toHaveCount(0);
      const cookie = (await page.context().cookies()).find((entry) =>
        entry.name === "__Host-portfolio_lab_session" || entry.name === "portfolio_lab_session")!;
      const auth = { Authorization: "FirebaseSession " + cookie.value };
      expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(200);
      expect((await page.request.post("/api/vor/bookings", { headers: { Origin: site }, data: {} })).status()).toBe(403);
      expect((await page.request.get(backend + "/api/vor/bootstrap", { headers: auth })).status()).toBe(200);
      expect((await page.request.get(backend + "/api/workforce/status", { headers: auth })).status()).toBe(403);
      expect((await page.request.post(backend + "/api/vor/bookings", { headers: auth, data: {} })).status()).toBe(403);

      const revoke = await owner.post(site + "/auth/access/grants", {
        headers: { Origin: site }, data: { ...change, role: "No Access", revision: 1 },
      });
      expect(revoke.status()).toBe(200);
      expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(403);
      expect((await page.request.get(backend + "/api/vor/bootstrap", { headers: auth })).status()).toBe(403);
      await page.reload();
      await expect(page.getByRole("status")).toContainText("No access has been assigned");
      const recruitment = await owner.post(site + "/auth/access/grants", {
        headers: { Origin: site },
        data: { uid, projectId: "workforce_intelligence", role: "View", revision: 0 },
      });
      expect(recruitment.status()).toBe(200);
      expect((await page.request.get("/portfolio/workforce-intelligence/api/status")).status()).toBe(200);
      expect((await page.request.get(backend + "/api/workforce/status", { headers: auth })).status()).toBe(200);
      expect((await page.request.post(backend + "/api/workforce/demo/reset", { headers: auth, data: {} })).status()).toBe(403);
      await page.reload();
      await expect(page.getByText("Workforce & Recruitment Intelligence", { exact: true })).toBeVisible();
      await expect(page.getByText("Fleet VOR Hub", { exact: true })).toHaveCount(0);
    } finally {
      await owner.dispose();
    }
  });

  test("one table row grants and revokes access for every linked login method", async ({ page, browser }) => {
    test.setTimeout(120_000);
    const suffix = randomBytes(6).toString("hex");
    const email = `linked-user-${suffix}@example.test`;
    const linkedEmails = { Microsoft: `microsoft-${suffix}@example.test`, Google: `google-${suffix}@example.test` };
    await page.goto("/sign-in");
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm password", { exact: true }).fill(password);
    const signup = page.waitForResponse((response) => response.url().includes("accounts:signUp"));
    await page.getByRole("button", { name: "Create account with email", exact: true }).click();
    const { localId: uid } = await (await signup).json();
    await page.getByRole("heading", { name: "Settings", exact: true }).waitFor();
    await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Profile", exact: true }).click();
    await expect(page.getByRole("button", { name: "Use Microsoft photo", exact: true })).toHaveCount(0);
    await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Login methods", exact: true }).click();
    for (const [name, linkedEmail] of Object.entries(linkedEmails)) {
      await mockProvider(page, "Link " + name, linkedEmail);
      await mockProvider(page, "Confirm " + name, linkedEmail);
      await expect(page.getByRole("status").filter({ hasText: name + " is linked" })).toBeVisible();
    }

    await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Profile", exact: true }).click();
    await expect(page.getByRole("button", { name: "Use Microsoft photo", exact: true })).toBeVisible();

    const owner = await browser.newContext({ baseURL: site, viewport: page.viewportSize() });
    try {
      await ownerSession(owner.request);
      const admin = await owner.newPage();
      const row = await findUserRow(admin, uid);
      await expect(row).toHaveCount(1);
      await expect(row.getByText("Email & password", { exact: true })).toBeVisible();
      for (const [name, linkedEmail] of Object.entries(linkedEmails)) {
        await expect(row.getByText(name, { exact: true })).toBeVisible();
        await expect(row.getByText(linkedEmail, { exact: true })).toBeVisible();
      }
      const role = row.getByRole("combobox", { name: `Fleet VOR Hub access for ${email}`, exact: true });
      await expect(role).toHaveValue("No Access");
      await role.selectOption("View");
      await role.locator("xpath=ancestor::form").getByRole("button", { name: "Save access" }).click();
      await expect(row.getByRole("status")).toHaveText("View access saved.");
      expect(await admin.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();

      for (const [name, linkedEmail] of Object.entries(linkedEmails)) {
        const signedOut = page.waitForResponse((response) =>
          response.url().endsWith("/auth/session") && response.request().method() === "DELETE", { timeout: 15_000 });
        await page.getByRole("button", { name: "Log Out", exact: true }).click();
        expect((await signedOut).status()).toBe(200);
        await page.getByRole("button", { name: "Continue with " + name, exact: true }).waitFor();
        await mockProvider(page, "Continue with " + name, linkedEmail);
        await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Login methods", exact: true }).click();
        await expect(page.getByText("Logged in with " + name, { exact: true })).toBeVisible();
        await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Available projects", exact: true }).click();
        await expect(page.getByText("View access", { exact: true })).toBeVisible();
        expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(200);
        expect((await page.request.get("/portfolio/workforce-intelligence/api/status")).status()).toBe(403);
      }
      await page.getByRole("button", { name: "Log Out", exact: true }).click();
      await page.getByLabel("Email", { exact: true }).fill(email);
      await page.getByLabel("Password", { exact: true }).fill(password);
      await page.getByRole("button", { name: "Log In with email", exact: true }).click();
      await expect(page.getByText("View access", { exact: true })).toBeVisible();
      expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(200);

      await role.selectOption("No Access");
      await role.locator("xpath=ancestor::form").getByRole("button", { name: "Save access" }).click();
      await expect(row.getByRole("status")).toHaveText("Access revoked.");
      expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(403);
      for (const [name, linkedEmail] of Object.entries(linkedEmails)) {
        await page.getByRole("button", { name: "Log Out", exact: true }).click();
        await page.getByRole("button", { name: "Continue with " + name, exact: true }).waitFor();
        await mockProvider(page, "Continue with " + name, linkedEmail);
        await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Login methods", exact: true }).click();
        await expect(page.getByText("Logged in with " + name, { exact: true })).toBeVisible();
        await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Available projects", exact: true }).click();
        expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(403);
      }
    } finally {
      await owner.close();
    }
  });

  for (const name of ["Google", "Microsoft", "GitHub", "Facebook"]) {
    test(`first ${name} sign-in remains logged in while awaiting project access`, async ({ page }) => {
      test.skip(name === "GitHub" && process.env.NEXT_PUBLIC_FIREBASE_GITHUB_ENABLED !== "true",
        "GitHub controls are disabled until the provider is configured");
      await page.goto("/sign-in");
      await mockProvider(page, "Continue with " + name, name.toLowerCase() + "-" + randomBytes(6).toString("hex") + "@example.test");
      await page.getByRole("heading", { name: "Settings", exact: true }).waitFor();
      await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Login methods", exact: true }).click();
      await expect(page.getByText("Logged in with " + name, { exact: true })).toBeVisible();
      await page.getByRole("navigation", { name: "Settings sections" }).getByRole("link", { name: "Available projects", exact: true }).click();
      await expect(page.getByRole("status")).toContainText("No access has been assigned");
      await expect(page.getByRole("link", { name: "Open" })).toHaveCount(0);
      expect((await page.request.get("/auth/session")).status()).toBe(200);
      expect((await page.request.get("/api/vor/bootstrap")).status()).toBe(403);
    });
  }
});
