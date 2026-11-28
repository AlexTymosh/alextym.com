import { expect, test } from "@playwright/test";

test("SamePlace decor endpoints remain private and disabled by default", async ({ request }) => {
  const base = "/portfolio/sameplace/api/rooms/friday/decor";
  expect((await request.get(base)).status()).toBe(404);
  for (const action of ["publish", "save_template", "delete_template", "music"]) {
    expect((await request.post(`${base}/${action}`, { data: {} })).status()).toBe(404);
  }
});
