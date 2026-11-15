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
const bff = read("frontend/lib/portfolio-lab/workforce-bff-server.ts");
for (const path of ["status", "[...operation]"]) {
  const adapter = read(`frontend/app/portfolio/workforce-intelligence/api/${path}/route.ts`);
  assert.match(adapter, /return forwardWorkforceRequest\(request,/);
}
assert.match(bff, /getWorkforceAccess\(sessionCookie\)/);
assert.match(bff, /FirebaseSession \$\{sessionCookie\}/);
assert.match(bff, /hasSameOrigin\(request\)/);
assert.match(bff, /workforceUpstreamPath\(/);
const dockerfile = read("backend/Dockerfile");
assert.match(dockerfile, /COPY portfolio\/workforce_intelligence\/backend\/src/);
const previewRoute = read("frontend/app/portfolio/workforce-intelligence/preview/page.tsx");
assert.match(previewRoute, /NODE_ENV\s*!==\s*"development"/);
assert.match(previewRoute, /WORKFORCE_LOCAL_PREVIEW\s*!==\s*"true"/);
assert.match(previewRoute, /Boolean\(process\.env\.VERCEL\)/);
assert.match(previewRoute, /<WorkforceScaffold previewMode/);
assert.match(previewRoute, /notFound\(\)/);
assert.doesNotMatch(previewRoute, /getWorkforceAccess|FirebaseSession/);
const ui = read("portfolio/workforce_intelligence/frontend/src/WorkforceScaffold.tsx");
assert.match(ui, /if \(previewMode\) return;/);
assert.match(ui, /workforceModeHref\(destination, previewMode\)/);

console.log("Workforce foundation: project grant wiring and default-off guard (structural PASS).");
