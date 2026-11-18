#!/usr/bin/env node

// Structural checks for the flag-controlled Firebase and legacy password gateways.
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

const portfolio = read("frontend/app/portfolio/page.tsx");
const page = read("frontend/app/portfolio/workforce-intelligence/page.tsx");
for (const source of [portfolio, page]) {
  assert.match(source, /robots:\s*\{\s*index:\s*false,\s*follow:\s*false/);
}
assert.doesNotMatch(portfolio, /firebase|getWorkforceAccess|LAB_SESSION_COOKIE/);
assert.match(portfolio, /href="\/fleet-vor-hub"/);
assert.match(portfolio, /href="\/portfolio\/workforce-intelligence"/);
assert.doesNotMatch(portfolio, /workforceEnabled\(|notFound\(/);
assert.match(page, /workforceEnabled\(/);
assert.match(page, /notFound\(\)/);
assert.match(page, /<WorkforcePasswordGate/);
assert.match(page, /await requireLabProjectPage\("workforce_intelligence"\)/);
assert.match(page, /loginPath=\{isLabEnabled\(\) \? "\/lab\/login" : undefined\}/);
const gate = read("portfolio/workforce_intelligence/frontend/src/WorkforcePasswordGate.tsx");
assert.match(gate, /workforce-simulation-logo\.png/);
assert.match(gate, /Demo password/);
const main = read("backend/app/main.py");
assert.match(main, /include_router\(workforce_access_router, prefix="\/api"\)/);
assert.match(main, /include_router\(\s*workforce_router,\s*prefix="\/api",\s*dependencies=\[Depends\(require_workforce_member\)\]\s*\)/);
assert.match(main, /from app\.security\.workforce_demo import/);
assert.doesNotMatch(main, /from app\.security\.project_grants import require_workforce_member/);
const security = read("backend/app/security/workforce_demo.py");
assert.match(security, /VOR_DEMO_PASSWORD/);
assert.match(security, /hmac\.compare_digest/);
assert.match(security, /request\.state\.workforce_uid/);
assert.match(security, /require_project_access\(request, WORKFORCE_PROJECT_ID\)/);
assert.match(security, /if os\.getenv\("PORTFOLIO_LAB_ENABLED"\) == "true":/);
assert.match(security, /@router\.post\("\/login"\)[\s\S]*?if os\.getenv\("PORTFOLIO_LAB_ENABLED"\) == "true":\s+raise HTTPException\(404, "Not found"\)/,
  "Legacy password login must be unavailable when Firebase authorization is enabled");
assert.doesNotMatch(security, /firebase_admin|from app\.security\.firebase/);
const bff = read("frontend/lib/portfolio-lab/workforce-bff-server.ts");
assert.match(bff, /const lab = isLabEnabled\(\)/);
assert.match(bff, /request\.cookies\.get\(lab \? LAB_SESSION_COOKIE : WORKFORCE_COOKIE\)/);
assert.match(bff, /labProjectAccess\(sessionCookie, "workforce_intelligence", request\.method, path\)/);
assert.match(bff, /if \(access\.status !== 200\) return reply\(access\.status,/);
assert.match(bff, /Authorization: `\$\{lab \? "FirebaseSession" : "WorkforceDemo"\} \$\{sessionCookie\}`/);
assert.match(bff, /workforceEnabled\(\)/);
assert.match(bff, /hasWorkforceOrigin\(request\)/);
assert.match(bff, /workforceUpstreamPath\(/);
for (const path of ["status", "[...operation]"]) {
  const adapter = read(`frontend/app/portfolio/workforce-intelligence/api/${path}/route.ts`);
  assert.match(adapter, /return forwardWorkforceRequest\(request,/);
}
const access = read("frontend/app/portfolio/workforce-intelligence/api/access/route.ts");
assert.match(access, /WORKFORCE_COOKIE/);
assert.match(access, /httpOnly: true/);
assert.match(access, /hasWorkforceOrigin\(request\)/);
const origin = read("frontend/lib/portfolio-lab/workforce-origin.ts");
assert.match(origin, /headers\.get\("host"\)/);
assert.doesNotMatch(origin, /PORTFOLIO_LAB_ORIGIN|x-forwarded-host/);
const dockerfile = read("backend/Dockerfile");
assert.match(dockerfile, /COPY portfolio\/workforce_intelligence\/backend\/src/);
const preview = read("frontend/app/portfolio/workforce-intelligence/preview/page.tsx");
assert.match(preview, /NODE_ENV\s*!==\s*"development"/);
assert.match(preview, /WORKFORCE_LOCAL_PREVIEW\s*!==\s*"true"/);
assert.match(preview, /Boolean\(process\.env\.VERCEL\)/);
assert.match(preview, /<WorkforceScaffold previewMode/);
assert.match(preview, /notFound\(\)/);
assert.doesNotMatch(preview, /WorkforcePasswordGate|FirebaseSession/);
const scaffold = read("portfolio/workforce_intelligence/frontend/src/WorkforceScaffold.tsx");
assert.match(scaffold, /if \(previewMode\) return;/);
assert.match(scaffold, /workforceModeHref\(id, previewMode\)/);
assert.match(scaffold, /workforceModeHref\(mode, previewMode, destination\)/);
console.log("Workforce Firebase/legacy password guards and project boundaries (structural PASS).");
