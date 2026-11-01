import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

/**
 * Browser smoke for an authenticated Fleet workspace. The API is deliberately
 * mocked here: server-side password, cookie and CSRF security remain covered
 * by the real FastAPI TestClient suite, using disposable SQLite databases.
 * Never provide a production/demo credential to Playwright.
 */
async function mockAuthenticatedFleet(page: Page) {
  let authenticated = true;
  const requests: string[] = [];
  const unexpected: string[] = [];

  const bootstrap = {
    today: "2026-11-01",
    workflows: [],
    vehicles: [
      {
        id: 1,
        registration: "GX24 KLM",
        model: "Synthetic ambulance",
        availability_status: "VOR",
        severity: "high",
        issue: "Synthetic engine alert",
        scenario: "engine",
        garage: "Basingstoke",
        vor_days: 2,
        workflow_current_step: 0,
        next_action: "Arrange inspection",
        responsible: "Jason W.",
        action_due: "2026-11-02",
        mot_due: "2026-12-20",
        inspection_due: "2026-12-22",
        service_due: "2026-12-30",
        odometer_miles: 12345,
        unread_count: 0,
      },
    ],
    tickets: [
      {
        id: "PS000001",
        vehicle_id: 1,
        kind: "defect",
        title: "Synthetic engine alert",
        status: "open",
        severity: "high",
        scenario: "engine",
        key2_reference: null,
        hoth_reference: null,
      },
    ],
    events: [],
    steps: [{ ticket_id: "PS000001", step_index: 0, label: "Notification", status: "current" }],
    contacts: [],
    subscriptions: [],
    bookings: [],
    daily: [
      { date: "2026-10-31", vor_count: 1, fleet_count: 1 },
      { date: "2026-11-01", vor_count: 1, fleet_count: 1 },
    ],
  };

  await page.route("**/api/vor/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    requests.push(`${method} ${url.pathname}`);
    let status = 200;
    let payload: unknown;

    switch (`${method} ${url.pathname}`) {
      case "GET /api/vor/session":
        payload = { enabled: true, authenticated, liveEmail: false };
        break;
      case "GET /api/vor/bootstrap":
        status = authenticated ? 200 : 401;
        payload = authenticated ? bootstrap : { detail: "Password required" };
        break;
      case "GET /api/vor/ops/overview":
        payload = { vehicles: {} };
        break;
      case "GET /api/vor/ops/details":
        // The Issue Hub mounts OperationsPanel for the selected vehicle/ticket.
        // Keep this mock explicit; unknown endpoints must still fail closed.
        if (url.searchParams.get("vehicle_id") !== "1" ||
            url.searchParams.get("ticket_id") !== "PS000001") {
          unexpected.push(`${method} ${url.pathname} (unexpected case reference)`);
          status = 400;
          payload = { detail: "Unexpected Fleet case reference" };
          break;
        }
        status = authenticated ? 200 : 401;
        payload = authenticated
          ? {
              actions: [], blockers: [], documents: [], release: [], audit: [],
              status: { availability_status: "VOR", registration: "GX24 KLM" },
              skips: [],
            }
          : { detail: "Password required" };
        break;
      case "GET /api/vor/ops/templates":
      case "GET /api/vor/checklists/PS000001":
        payload = { items: [] };
        break;
      case "POST /api/vor/logout":
        authenticated = false;
        payload = { ok: true };
        break;
      default:
        unexpected.push(`${method} ${url.pathname}`);
        status = 501;
        payload = { detail: `Unexpected mocked Fleet API request: ${method} ${url.pathname}` };
    }

    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });
  });
  return { requests, unexpected };
}

test("authenticated Fleet workspace retains project-owned navigation", async ({ page }) => {
  const { requests, unexpected } = await mockAuthenticatedFleet(page);
  const response = await page.goto("/fleet-vor-hub");
  expect(response?.status()).toBe(200);

  await expect(page.getByRole("heading", { name: "Issue Hub", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(page.getByLabel("Fleet VOR Hub navigation")).toBeVisible();
  await expect(page.getByRole("heading", { name: "GX24 KLM" })).toBeVisible();

  await page.getByRole("button", { name: "Process Design", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Defect handling" })).toBeVisible();
  await page.getByRole("button", { name: "Issue Hub", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Issue Hub", exact: true })).toBeVisible();

  expect(requests).toContain("GET /api/vor/session");
  expect(requests).toContain("GET /api/vor/bootstrap");
  expect(requests).not.toContain("POST /api/vor/login");
  expect(unexpected).toEqual([]);
});

test("sign-out returns to access screen and removes authenticated navigation", async ({ page }) => {
  const { requests, unexpected } = await mockAuthenticatedFleet(page);
  await page.goto("/fleet-vor-hub");
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page.getByLabel("Demo password")).toBeVisible();
  await expect(page.getByLabel("Fleet VOR Hub navigation")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Sign out" })).toHaveCount(0);
  expect(requests.filter((x) => x === "POST /api/vor/logout")).toHaveLength(1);
  expect(unexpected).toEqual([]);
});
