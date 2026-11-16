import { expect, test } from "@playwright/test";
import { workforceUpstreamPath } from "../lib/portfolio-lab/workforce-transport";
import { hasWorkforceOrigin } from "../lib/portfolio-lab/workforce-origin";
import { MAX_WORKBOOK_BYTES, readWorkbookBytes } from "../lib/portfolio-lab/workforce-workbooks";

test("the Vercel password gate accepts its HTTPS site without Portfolio Lab configuration", () => {
  function forwarded(origin: string, forwardedHost = "alextym.com") {
    return new Request("http://localhost:3000/portfolio/workforce-intelligence/api/access", {
      method: "POST", headers: { origin, host: "alextym.com", "x-forwarded-host": forwardedHost },
    });
  }
  expect(hasWorkforceOrigin(forwarded("https://alextym.com"), true)).toBe(true);
  expect(hasWorkforceOrigin(forwarded("https://outside.example", "outside.example"), true)).toBe(false);
  expect(hasWorkforceOrigin(forwarded("http://alextym.com"), true)).toBe(false);
  expect(hasWorkforceOrigin(forwarded("https://alextym.com/other"), true)).toBe(false);
  expect(hasWorkforceOrigin(new Request("http://localhost:14300/api/access", {
    headers: { host: "127.0.0.1:14300", origin: "http://127.0.0.1:14300" },
  }), false)).toBe(true);
});

test("the public portfolio has working links to both demos", async ({ page }) => {
  await page.goto("/portfolio/");
  await expect(page.locator(".site-header")).toBeVisible();
  await expect(page.locator(".site-footer")).toBeVisible();
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Portfolio demonstrations" })).toBeVisible();
  await expect(main.getByRole("link", { name: /Fleet VOR Hub/ })).toHaveAttribute("href", "/fleet-vor-hub");
  await expect(main.getByRole("link", { name: /Workforce & Recruitment Intelligence/ }))
    .toHaveAttribute("href", "/portfolio/workforce-intelligence");
});

test("maps only approved Workforce operation and filter combinations", () => {
  const query = new URLSearchParams({ vacancy_id: "vac-001", as_of_date: "2026-10-31" });
  expect(workforceUpstreamPath("GET", ["analytics", "candidate-funnel"], query)).toBe(
    "/api/workforce/analytics/candidate-funnel?vacancy_id=vac-001&as_of_date=2026-10-31",
  );
  expect(workforceUpstreamPath("PATCH", ["employees", "emp-001", "contracts"], new URLSearchParams())).toBe(
    "/api/workforce/employees/emp-001/contracts",
  );
});

test("rejects path traversal, unapproved operations, and target overrides", () => {
  const empty = new URLSearchParams();
  expect(workforceUpstreamPath("GET", ["status\n"], empty)).toBeNull();
  expect(workforceUpstreamPath("GET", ["..", "lab", "identity"], empty)).toBeNull();
  expect(workforceUpstreamPath("PATCH", ["employees", "emp%2f001", "contracts"], empty)).toBeNull();
  expect(workforceUpstreamPath("GET", ["https:", "untrusted.example"], empty)).toBeNull();
  expect(workforceUpstreamPath("GET", ["demo", "reset"], empty)).toBeNull();
  expect(workforceUpstreamPath("POST", ["demo", "reset"], new URLSearchParams("url=https://untrusted.example"))).toBeNull();
  expect(workforceUpstreamPath("GET", ["employees"], new URLSearchParams("limit=5&limit=15"))).toBeNull();
});

test("planning and architecture allow only their expected queries and methods", () => {
  const empty = new URLSearchParams();
  const run = "53d71d60-7483-473c-83e0-89ab63b9672b";
  expect(workforceUpstreamPath("GET", ["forecast", "history"], new URLSearchParams("metric=vacancy_wte")))
    .toBe("/api/workforce/forecast/history?metric=vacancy_wte");
  expect(workforceUpstreamPath("POST", ["forecast"], empty)).toBe("/api/workforce/forecast");
  expect(workforceUpstreamPath("GET", ["scenarios", run], empty)).toBe(`/api/workforce/scenarios/${run}`);
  expect(workforceUpstreamPath("POST", ["scenarios", run], empty)).toBeNull();
  expect(workforceUpstreamPath("GET", ["scenarios", "other-site"], empty)).toBeNull();
  expect(workforceUpstreamPath("GET", ["architecture", "layers"], new URLSearchParams("table=employees"))).toBeNull();
});

test("the live browser route rejects an unsigned Workforce data request", async ({ request }) => {
  const response = await request.get("/portfolio/workforce-intelligence/api/analytics/executive", {
    headers: { Authorization: "WorkforceDemo forged" },
  });
  expect([401, 404, 503]).toContain(response.status());
  expect(response.headers()["cache-control"]).toBe("no-store");
  expect(await response.json()).toEqual({ detail: expect.any(String) });
});
test("workbook transport allows only named operations and bounds a streamed body", async () => {
  const query = new URLSearchParams();
  const batch = "53d71d60-7483-473c-83e0-89ab63b9672b";
  expect(workforceUpstreamPath("POST", ["import", "validate"], query)).toBe("/api/workforce/import/validate");
  expect(workforceUpstreamPath("GET", ["import", batch, "errors"], query)).toBe(`/api/workforce/import/${batch}/errors`);
  expect(workforceUpstreamPath("GET", ["import", "data", "errors"], query)).toBeNull();
  expect(workforceUpstreamPath("POST", ["import", "template"], query)).toBeNull();
  expect(workforceUpstreamPath("POST", ["export"], new URLSearchParams("origin=somewhere"))).toBeNull();
  const bytes = await readWorkbookBytes(new Response(new Uint8Array([0x50, 0x4b])));
  expect(bytes instanceof ArrayBuffer && new Uint8Array(bytes)[0]).toBe(0x50);
  const oversized = new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(MAX_WORKBOOK_BYTES));
      controller.enqueue(new Uint8Array([0]));
      controller.close();
    },
  }));
  expect(await readWorkbookBytes(oversized)).toBe("too_large");
});
