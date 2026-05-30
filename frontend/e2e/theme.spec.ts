import { expect, test, type Page } from "@playwright/test";

const storageKey = "alextym-theme";

async function resetTheme(page: Page) {
  await page.evaluate((key) => {
    localStorage.removeItem(key);
    document.documentElement.dataset.theme = "dark";
  }, storageKey);
}

async function readRootThemeTokens(page: Page) {
  return page.evaluate(() => {
    const styles = getComputedStyle(document.documentElement);

    return {
      background: styles.getPropertyValue("--bg").trim().toLowerCase(),
      previewGlow: styles
        .getPropertyValue("--project-preview-glow")
        .trim()
        .toLowerCase(),
      surface: styles.getPropertyValue("--surface").trim().toLowerCase(),
    };
  });
}

test("switches to light theme and persists the choice", async ({ page }) => {
  await page.goto("/");
  await resetTheme(page);
  await page.reload();

  const html = page.locator("html");

  await expect(html).toHaveAttribute("data-theme", "dark");

  await page.getByRole("button", { name: /switch to light mode/i }).click();

  await expect(html).toHaveAttribute("data-theme", "light");
  await expect(
    page.getByRole("button", { name: /switch to dark mode/i }),
  ).toBeVisible();

  await expect
    .poll(async () => page.evaluate((key) => localStorage.getItem(key), storageKey))
    .toBe("light");

  const tokens = await readRootThemeTokens(page);

  expect(tokens.background).toBe("#f6f5f2");
  expect(tokens.previewGlow).not.toBe("");
  expect(["#fff", "#ffffff"]).toContain(tokens.surface);

  await page.reload();

  await expect(html).toHaveAttribute("data-theme", "light");
  await expect(
    page.getByRole("button", { name: /switch to dark mode/i }),
  ).toBeVisible();

  await expect
    .poll(async () => page.evaluate((key) => localStorage.getItem(key), storageKey))
    .toBe("light");
});
