import { expect, test } from "@playwright/test";

test("SamePlace remains hidden and disabled without changing the site language", async ({ page }) => {
  await page.goto("/portfolio");
  const language = await page.locator("html").getAttribute("lang");
  if (!language) throw new Error("Host language missing");
  await expect(page.getByRole("link", { name: /sameplace/i })).toHaveCount(0);
  const response = await page.goto("/portfolio/sameplace");
  expect(response?.status()).toBe(404);
  await expect(page.locator("#sameplace-title")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("lang", language);
  await page.goto("/portfolio");
  await expect(page.locator("html")).toHaveAttribute("lang", language);
});
