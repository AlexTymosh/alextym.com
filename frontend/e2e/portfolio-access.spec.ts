import { expect, test } from "@playwright/test";
import { publicProjects } from "../lib/portfolio-lab/project-catalog";

test("public case studies and screenshots preserve guest denial for both projects", async ({ page, request }) => {
  test.skip(process.env.PORTFOLIO_LAB_ENABLED !== "true" || process.env.WORKFORCE_INTELLIGENCE_ENABLED !== "true",
    "Requires both projects enabled in the existing Firebase access mode");
  const protectedRequests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/vor/") || path.startsWith("/api/workforce/") ||
        path.startsWith("/portfolio/workforce-intelligence/api/")) protectedRequests.push(path);
  });
  expect((await page.goto("/portfolio"))?.status()).toBe(200);
  for (const project of publicProjects) {
    const card = page.getByRole("article", { name: project.title, exact: true });
    await expect(card).toBeVisible();
    const screenshot = await card.getByRole("link", { name: /screenshot/ }).getAttribute("href");
    expect((await request.get(screenshot!)).status()).toBe(200);
    const denied = await request.get(project.path, { maxRedirects: 0 });
    expect(denied.status()).toBe(307);
    expect(denied.headers().location).toBe("/sign-in");
  }
  expect(protectedRequests).toEqual([]);
  for (const api of ["/api/vor/bootstrap", "/portfolio/workforce-intelligence/api/status"]) {
    expect((await request.get(api)).status()).toBe(401);
  }
});
