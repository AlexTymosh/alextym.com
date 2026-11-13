#!/usr/bin/env node

// Explicit, CI-friendly pre-RBAC contract. This check is structural, not a runtime security proof.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const read = (file) => readFileSync(resolve(root, file), "utf8");
const registry = JSON.parse(read("portfolio/catalog/registry.json"));
const manifest = JSON.parse(read("portfolio/workforce_intelligence/project.json"));
assert.ok(registry.projectIds.includes("workforce_intelligence"));
assert.equal(manifest.id, "workforce_intelligence");
assert.equal(manifest.demo.path, "/portfolio/workforce-intelligence");
assert.equal(manifest.demo.apiPrefix, "/api/workforce");
assert.deepEqual(manifest.catalog, { visible: false, featured: false });

for (const path of [
  "frontend/app/portfolio/page.tsx",
  "frontend/app/portfolio/workforce-intelligence/page.tsx",
]) {
  const content = read(path);
  assert.match(content, /notFound\(\)/, `${path}: expected disabled route`);
  assert.match(content, /robots:\s*\{\s*index:\s*false,\s*follow:\s*false/);
}
const router = read("portfolio/workforce_intelligence/backend/src/workforce_intelligence/router.py");
assert.match(router, /raise HTTPException\(status_code=404/);
const host = read("backend/app/main.py");
assert.match(host, /include_router\(workforce_router, prefix="\/api"\)/);
const dockerfile = read("backend/Dockerfile");
assert.match(dockerfile, /COPY portfolio\/workforce_intelligence\/backend\/src/);
console.log("Workforce foundation: registered, isolated and closed (structural checks PASS).");
