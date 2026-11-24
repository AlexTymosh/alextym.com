#!/usr/bin/env node

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const read = (path) => readFileSync(join(root, path), "utf8");
const registry = JSON.parse(read("portfolio/catalog/registry.json"));
const manifest = JSON.parse(read("portfolio/preferans/project.json"));
const routes = read("frontend/app/portfolio/preferans/page.tsx");
const tsconfig = JSON.parse(read("frontend/tsconfig.json"));
const localized = JSON.parse(read("portfolio/preferans/frontend/src/content.ru.json"));
const shell = read("portfolio/preferans/frontend/src/PreferansWelcome.tsx");

assert.ok(registry.projectIds.includes("preferans"), "Module must be registered");
assert.equal(manifest.id, "preferans");
assert.equal(manifest.slug, "preferans");
assert.equal(manifest.demo.path, "/portfolio/preferans");
assert.equal(manifest.demo.apiPrefix, "/api/preferans");
assert.equal(manifest.catalog.visible, true, "Portfolio card must be visible");
assert.deepEqual(tsconfig.compilerOptions.paths["@preferans"], ["../portfolio/preferans/frontend/src/index.ts"]);
assert.match(routes, /from\s+["']@preferans["']/);
assert.match(routes, /if\s*\(!isLabEnabled\(\)\)\s*notFound\(\)/);
assert.match(routes, /await requireLabProjectPage\(["']preferans["']\)/);
assert.match(routes, /robots:\s*\{\s*index:\s*false,\s*follow:\s*false\s*\}/);
assert.ok(localized.title.length > 0);
assert.match(shell, /content\.ru\.json/);
assert.doesNotMatch(shell, /fetch\(|localStorage|firebase-admin|@fleet-hub|@workforce-intelligence/);

function checkCyrillic(relative) {
  for (const entry of readdirSync(join(root, relative), { withFileTypes: true })) {
    if (entry.isSymbolicLink()) continue;
    const local = `${relative}/${entry.name}`;
    if (entry.isDirectory()) {
      checkCyrillic(local);
    } else if (entry.isFile()) {
      const name = basename(local).toLowerCase();
      const text = read(local);
      if (/[\u0400-\u04ff]/u.test(text)) {
        assert.ok(name.includes(".ru.") || name.endsWith(".ru"),
          `${local}: raw Cyrillic must be in a .ru. file`);
      }
    }
  }
}
checkCyrillic("portfolio/preferans");

console.log("Preferans foundation: PASS (registered, unpublished, route gated, local UI)");
