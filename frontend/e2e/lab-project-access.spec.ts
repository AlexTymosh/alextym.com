import { expect, test } from "@playwright/test";
import { grantChange } from "../lib/portfolio-lab/grant-change";
import { projectGrantRole, projectRoleAllows } from "../lib/portfolio-lab/project-grants";

const now = 1_800_000_000_000;
const grant = { schema_version: 1, uid: "user", project_id: "fleet_hub", role: "View", status: "active" };

test("project grants are UID-bound, isolated, revocable and expire at their cutoff", () => {
  expect(projectGrantRole("user", "fleet_hub", grant, now)).toBe("View");
  expect(projectGrantRole("other", "fleet_hub", grant, now)).toBeNull();
  expect(projectGrantRole("user", "workforce_intelligence", grant, now)).toBeNull();
  expect(projectGrantRole("user", "fleet_hub", { ...grant, status: "revoked" }, now)).toBeNull();
  expect(projectGrantRole("user", "fleet_hub", { ...grant, expires_at_ms: now }, now)).toBeNull();
  expect(projectGrantRole("user", "fleet_hub", { ...grant, expires_at_ms: now + 1 }, now)).toBe("View");
  expect(projectGrantRole("user", "fleet_hub", { ...grant, role: "Owner" }, now)).toBeNull();
});

for (const [role, read, write, reset] of [
  ["View", true, false, false], ["Test", true, true, false], ["Admin", true, true, true],
] as const) {
  test(`${role} has the intended project capabilities`, () => {
    expect(projectRoleAllows(role, "GET", "/api/vor/bootstrap")).toBe(read);
    expect(projectRoleAllows(role, "POST", "/api/vor/bookings")).toBe(write);
    expect(projectRoleAllows(role, "POST", "/api/workforce/demo/reset")).toBe(reset);
    expect(projectRoleAllows(role, "POST", "/api/vor/workflows/create")).toBe(reset);
  });
}

test("missing access and malformed Owner edits cannot become a project grant", () => {
  expect(projectRoleAllows(null, "GET", "/api/vor/bootstrap")).toBe(false);
  const command = { uid: "user", projectId: "fleet_hub", role: "View", revision: 0 };
  expect(grantChange(command, ["fleet_hub"])).toEqual(command);
  for (const invalid of [
    { ...command, role: "Owner" }, { ...command, projectId: "unknown" },
    { ...command, revision: -1 }, { ...command, uid: "../owner" },
    { ...command, actor_uid: "owner" },
  ]) expect(grantChange(invalid, ["fleet_hub"])).toBeNull();
});
