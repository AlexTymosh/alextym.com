import { expect, test } from "@playwright/test";
import { workforceUpstreamPath } from "../lib/portfolio-lab/workforce-transport";

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

test("the live browser route rejects an unsigned Workforce data request", async ({ request }) => {
  const response = await request.get("/portfolio/workforce-intelligence/api/analytics/executive", {
    headers: { Authorization: "FirebaseSession forged" },
  });
  expect([401, 404, 503]).toContain(response.status());
  expect(response.headers()["cache-control"]).toBe("no-store");
  expect(await response.json()).toEqual({ detail: expect.any(String) });
});
