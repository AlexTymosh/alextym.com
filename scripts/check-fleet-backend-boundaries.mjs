#!/usr/bin/env node

// Read-only architecture and data-integrity contract for Fleet PR 3.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const owned = "portfolio/fleet_hub/backend/src/fleet_hub";
const api = ["vor", "vor_workflow_admin", "vor_reporting", "vor_reconciliation", "vor_operations", "vor_checklist", "vor_data", "vor_intake"];
const services = ["vor_data", "vor_exports", "vor_intake", "vor_operations", "vor_reconciliation", "vor_reporting", "vor_store", "vor_workflow_admin"];
const read = (file) => readFileSync(join(root, file), "utf8");
for (const [kind, names] of [["api", api], ["services", services]]) {
  for (const name of names) {
    const p = `${owned}/${kind}/${name}.py`;
    assert.ok(existsSync(join(root, p)), `Missing project-owned ${p}`);
    const content = read(p);
    assert.doesNotMatch(content, /from app\.(?:api|services)|import app\.(?:api|services)/, `${p} imports host business logic`);
    const shim = read(`backend/app/${kind}/${name}.py`);
    assert.ok(shim.length < 450, `Legacy ${kind}/${name} adapter contains implementation`);
    assert.ok(shim.includes(`fleet_hub.${kind}.${name}`));
  }
}
const router = read(`${owned}/router.py`);
for (const name of api) assert.ok(router.includes(`    ${name},`));
const main = read("backend/app/main.py");
assert.match(main, /from fleet_hub\.router import router as fleet_router/);
assert.equal((main.match(/app\.include_router\(fleet_router, prefix="\/api"\)/g) || []).length, 1);
assert.doesNotMatch(main, /app\.include_router\(vor(?:_\w+)?_router,/);
const docker = read("backend/Dockerfile");
assert.match(docker, /COPY portfolio\/fleet_hub\/backend\/src \/portfolio\/fleet_hub\/backend\/src/);
const config = read("backend/pyproject.toml");
assert.match(config, /\.\.\/portfolio\/fleet_hub\/tests/);
const seed = join(root, `${owned}/services/vor_seed.sqlite3`);
assert.ok(existsSync(seed));
const hash = createHash("sha256").update(readFileSync(seed)).digest("hex");
assert.equal(hash, "db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532");
const original = join(root, "backend/app/services/vor_seed.sqlite3");
assert.ok(!existsSync(original), "Seed must not remain in the host service package");
const tests = ["test_vor_checklist", "test_vor_contact_management", "test_vor_data_api_errors", "test_vor_data_foundation", "test_vor_demo", "test_vor_email_validation", "test_vor_intake", "test_vor_operations", "test_vor_reconciliation", "test_vor_reporting", "test_vor_seed_contract", "test_vor_seed_exports", "test_vor_subscribers", "test_vor_wildcard_regression", "test_vor_workflow_admin", "test_vor_workflow_owners"];
for (const name of tests) {
  assert.ok(existsSync(join(root, `portfolio/fleet_hub/tests/${name}.py`)), `Lost test ${name}`);
  assert.ok(!existsSync(join(root, `backend/tests/${name}.py`)), `Unmoved test ${name}`);
}
assert.ok(existsSync(join(root, "portfolio/fleet_hub/tests/test_fleet_module_wiring.py")), "Missing host-module wiring regression test");
console.log(`Fleet backend boundaries: PASS (${api.length} routers, ${services.length} services, ${tests.length} migrated tests + wiring, approved seed)`);
