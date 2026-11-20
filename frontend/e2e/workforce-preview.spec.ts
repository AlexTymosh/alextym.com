import { expect, test } from "@playwright/test";

const previewPath = "/portfolio/workforce-intelligence/preview";
const runLocalPreview =
  process.env.PLAYWRIGHT_USE_DEV_SERVER === "true" &&
  process.env.WORKFORCE_LOCAL_PREVIEW === "true";

test("local Workforce preview is closed during production and ordinary runs", async ({ request }) => {
  test.skip(runLocalPreview, "This run explicitly enables the development-only preview");
  const response = await request.get(previewPath);
  expect(response.status()).toBe(404);
});

test("local Workforce preview supports offline navigation without API requests", async ({ page }) => {
  test.skip(!runLocalPreview, "Requires a development server and explicit local preview flag");

  // React/Next dev-mode regression: root theme script must not be rendered
  // as an ordinary client-side <script> during preview navigation.
  const scriptWarnings: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" &&
        message.text().includes("Encountered a script tag while rendering React component")) {
      scriptWarnings.push(message.text());
    }
  });

  const protectedRequests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/workforce/") ||
        path.startsWith("/portfolio/workforce-intelligence/api/") ||
        path.startsWith("/auth/")) protectedRequests.push(path);
  });

  const response = await page.goto(previewPath);
  expect(response?.status()).toBe(200);
  await expect(page.getByText("Local UI preview — no Firebase or API calls")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workforce Intelligence", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry check" })).toHaveCount(0);

  await page.getByRole("link", { name: /People Voice/ }).click();
  await expect(page).toHaveURL(`${previewPath}?mode=people-voice`);
  await expect(page.getByRole("heading", { name: "People Voice" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "People Voice" })).toBeVisible();

  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
  expect(protectedRequests).toEqual([]);
  expect(scriptWarnings).toEqual([]);
});
