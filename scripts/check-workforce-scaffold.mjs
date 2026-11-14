#!/usr/bin/env node

// Structural guard: runtime tests separately prove grant authorization behavior.
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

for (const path of ["frontend/app/portfolio/page.tsx", "frontend/app/portfolio/workforce-intelligence/page.tsx"]) {
  const source = read(path);
  assert.match(source, /getWorkforceAccess\(/, `${path}: missing server grant guard`);
  assert.match(source, /notFound\(\)/, `${path}: missing fail-closed rendering`);
  assert.match(source, /robots:\s*\{\s*index:\s*false,\s*follow:\s*false/);
}
const main = read("backend/app/main.py");
assert.match(main, /include_router\(\s*workforce_router,\s*prefix="\/api",\s*dependencies=\[Depends\(require_workforce_member\)\]\s*\)/);
const policy = read("backend/app/security/project_grants.py");
assert.match(policy, /grant_document\(/);
assert.match(policy, /require_lab_identity\(request\)/);
assert.match(policy, /load_project_grant\(WORKFORCE_PROJECT_ID, uid\)/);
const bff = read("frontend/app/portfolio/workforce-intelligence/api/status/route.ts");
assert.match(bff, /getWorkforceAccess\(sessionCookie\)/);
assert.match(bff, /FirebaseSession \$\{sessionCookie\}/);
const dockerfile = read("backend/Dockerfile");
assert.match(dockerfile, /COPY portfolio\/workforce_intelligence\/backend\/src/);
console.log("Workforce foundation: project grant wiring and default-off guard (structural PASS).");
