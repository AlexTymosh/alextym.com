#!/usr/bin/env node

// Read-only boundary contract for the frontend move. Runs in the existing CI.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const siteRoute = join(root, "frontend/app/fleet-vor-hub");
const projectSource = join(root, "portfolio/fleet_hub/frontend/src");

function gather(dir, rel = "") {
  return readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = join(dir, d.name);
    const nested = join(rel, d.name);
    return d.isDirectory() ? gather(p, nested) : [nested.replaceAll("\\", "/")];
  });
}

assert.ok(existsSync(projectSource), "Missing Fleet Hub frontend implementation");
const siteFiles = gather(siteRoute).sort();
assert.deepEqual(siteFiles, [
  "new-defect/page.tsx",
  "page.tsx",
  "process/page.tsx",
  "register/page.tsx",
], "Next.js route folder should only contain public adapters/redirects");

const appFiles = gather(projectSource);
assert.ok(appFiles.filter((x) => x.endsWith(".tsx")).length >= 12, "Fleet components not moved");
assert.ok(appFiles.includes("vehicle-photo/assets/fleet-van-demo.webp"));
assert.ok(appFiles.includes("assets/alex.webp"));
assert.ok(appFiles.includes("index.ts"));

const page = readFileSync(join(siteRoute, "page.tsx"), "utf8");
assert.match(page, /from ["']@fleet-hub["']/);
assert.doesNotMatch(page, /\.\/FleetApp/);
const index = readFileSync(join(projectSource, "index.ts"), "utf8");
assert.match(index, /FleetHubApp/);

for (const rel of appFiles.filter((x) => x.endsWith(".tsx") || x.endsWith(".ts"))) {
  const contents = readFileSync(join(projectSource, rel), "utf8");
  assert.doesNotMatch(contents, /(?:from\s*["']|import\s*["'])[^"']*(?:frontend\/app|frontend\/components|frontend\/lib|backend\/app)[^"']*["']/, `${rel}: website-internal import is forbidden`);
  assert.doesNotMatch(contents, /["']\/images\/profile\/alex\.webp["']/, `${rel}: use a Fleet-owned asset`);
}

const tsconfig = JSON.parse(readFileSync(join(root, "frontend/tsconfig.json"), "utf8"));
assert.deepEqual(tsconfig.compilerOptions.paths["@fleet-hub"], ["../portfolio/fleet_hub/frontend/src/index.ts"]);
const config = readFileSync(join(root, "frontend/next.config.mjs"), "utf8");
assert.match(config, /root: resolve\(appRoot, "\.\."\)/);
const pkg = JSON.parse(readFileSync(join(root, "frontend/package.json"), "utf8"));
assert.equal(pkg.scripts.lint, "eslint . && node scripts/lint-fleet-module.mjs");
const fleetLintScript = readFileSync(join(root, "frontend/scripts/lint-fleet-module.mjs"), "utf8");
assert.match(fleetLintScript, /cwd: fleetRoot/);
assert.match(fleetLintScript, /--config/);
assert.match(fleetLintScript, /"src"/);
for (const hook of ["predev", "prebuild", "prelint", "pretypecheck", "pree2e", "pree2e:headed"]) {
  assert.ok(pkg.scripts[hook]?.includes("link-portfolio-deps.mjs"), `${hook} must connect project dependencies`);
}
const linkScript = readFileSync(join(root, "frontend/scripts/link-portfolio-deps.mjs"), "utf8");
assert.match(linkScript, /const link = join\(moduleRoot, "node_modules"\)/);
assert.doesNotMatch(linkScript, /const link = join\(repoRoot, "node_modules"\)/);
const manifest = JSON.parse(readFileSync(join(root, "portfolio/fleet_hub/project.json"), "utf8"));
assert.equal(manifest.catalog.visible, false);
assert.equal(manifest.demo.path, "/fleet-vor-hub");
assert.ok(existsSync(join(root, "backend/app/services/vor_seed.sqlite3")), "PR 2 must not move the SQLite seed");
console.log(`Fleet frontend boundary check passed (${appFiles.length} project-owned source/assets, four host routes).`);
