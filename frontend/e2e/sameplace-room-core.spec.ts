import { expect, test } from "@playwright/test";
test("private SamePlace room entrypoints and BFF stay disabled by default", async ({ page, request }) => {
  for (const path of ["/portfolio/sameplace/rooms", "/portfolio/sameplace/j", "/portfolio/sameplace/r/friday", `/portfolio/sameplace/j/${"a".repeat(32)}.${"B".repeat(43)}`]) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(404);
    await expect(page.locator("#sameplace-title")).toHaveCount(0);
  }
  expect((await request.get("/portfolio/sameplace/api/rooms")).status()).toBe(404);
});


test("SamePlace social and ticket routes are private and off by default", async ({ request }) => {
  const base = "/portfolio/sameplace/api";
  expect((await request.get(`${base}/social/me`)).status()).toBe(404);
  expect((await request.get(`${base}/rooms/friday/chat`)).status()).toBe(404);
  expect((await request.post(`${base}/rooms/friday/ticket`, {data:{origin:"https://example.invalid"}})).status()).toBe(404);
  expect((await request.post(`${base}/rooms/friday/ping`, {data:{}})).status()).toBe(404);
});
