#!/usr/bin/env node
// Project-owned static integration assertions. No node_modules or provider calls.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { resolve, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { BASELINE } from "./check-freeze.mjs";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const read = (path) => readFileSync(resolve(root, path), "utf8");
const old = (path) => execFileSync("git", ["show", `${BASELINE}:${path}`], { cwd: root, encoding: "utf8" });
const manifest = JSON.parse(read("portfolio/sameplace/project.json"));
assert.equal(manifest.id, "sameplace");
assert.equal(manifest.demo.path, "/portfolio/sameplace");
assert.equal(manifest.demo.apiPrefix, "/api/sameplace");
assert.equal(manifest.catalog.visible, false, "Publication needs explicit release approval");
const page = read("frontend/app/portfolio/sameplace/page.tsx");
assert.match(page, /from "\.\/client"/);
assert.match(read("frontend/app/portfolio/sameplace/client.tsx"), /from "@sameplace"/);
assert.match(page, /robots: \{ index: false, follow: false \}/);
assert.match(page, /if \(!isLabEnabled\(\) \|\| process\.env\.SAMEPLACE_ENABLED !== "true"\) notFound\(\)/);
assert.doesNotMatch(page, /requireLabProjectPage/);
assert.match(page, /<SamePlaceClient/);
assert.match(read("frontend/app/portfolio/sameplace/api/[...operation]/route.ts"), /hasSameOrigin\(request\)/);
const backend = read("backend/app/main.py");
assert.match(backend, /app\.include_router\(\s*sameplace_router, prefix="\/api", dependencies=\[Depends\(require_sameplace_member\)\]\s*\)/);
assert.match(backend, /app\.include_router\(\s*preferans_router, prefix="\/api", dependencies=\[Depends\(require_preferans_member\)\]\s*\)/);
assert.match(backend, /app\.include_router\(make_realtime_router\(verify_preferans_realtime\), prefix="\/api"\)/);
const beforeAliases = JSON.parse(old("frontend/tsconfig.json")).compilerOptions.paths;
const aliases = JSON.parse(read("frontend/tsconfig.json")).compilerOptions.paths;
assert.deepEqual(aliases["@preferans"], beforeAliases["@preferans"], "Legacy alias changed");
assert.deepEqual(aliases["@sameplace"], ["../portfolio/sameplace/frontend/src/index.ts"]);
const rules = read("infra/firebase/firestore.rules");
assert.match(rules, /match\s+\/\{document=\*\*\}\s*\{\s*allow read, write: if false;/);
assert.equal((rules.match(/\ballow\s+/g) || []).length, 1, "No direct browser permissions without review");
const rootLayout = read("frontend/app/layout.tsx");
assert.match(rootLayout, /<html lang=\{siteConfig\.language\}/, "Global site language remains host-owned");

function walk(path) {
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isSymbolicLink() || entry.name === "node_modules" || entry.name.startsWith(".")) return [];
    const full = resolve(path, entry.name);
    return entry.isDirectory() ? walk(full) : entry.isFile() ? [full] : [];
  });
}
const source = resolve(root, "portfolio/sameplace/frontend/src");
const declarations = /^[ \t]*(?:import|export)[ \t]+(?:type[ \t]+)?[\w*{}, \t\r\n]+?[ \t]+from[ \t]*["']([^"'\r\n]+)["']/gm;
const sideEffects = /^[ \t]*import[ \t]*["']([^"'\r\n]+)["']/gm;
const dynamic = /\b(?:import|require)\s*\(\s*["']([^"'\r\n]+)["']/g;
for (const file of walk(source)) {
  if ([".ts", ".tsx", ".js", ".jsx", ".mjs"].includes(extname(file))) {
    const content = readFileSync(file, "utf8");
    for (const pattern of [declarations, sideEffects, dynamic]) {
      for (const match of content.matchAll(pattern)) {
        const target = match[1];
        assert.ok(target.startsWith(".") || /^(?:react|next)(?:\/.*)?$/.test(target), `Unreviewed dependency: ${file}: ${target}`);
      }
    }
    assert.doesNotMatch(content, /\bdocument\.(?:documentElement|body)\b/, "Global DOM ownership is not allowed");
  }
  if (file.endsWith(".css")) {
    assert.ok(file.endsWith(".module.css"));
    assert.doesNotMatch(readFileSync(file, "utf8"), /(?:^|[{}\n])\s*(?:html|body|:root)\b\s*(?:[,#{.:\s]|\{)/m);
  }
}
for (const folder of ["frontend/app", "frontend/components"]) {
  for (const file of walk(resolve(root, folder))) {
    if (![".ts", ".tsx", ".js", ".jsx", ".mjs"].includes(extname(file))) continue;
    const content = readFileSync(file, "utf8");
    for (const pattern of [declarations, sideEffects, dynamic]) {
      for (const match of content.matchAll(pattern)) {
        const target = match[1];
        assert.doesNotMatch(target, /portfolio\/sameplace\/frontend\/src/, "Host must use the public entrypoint");
        if (/^@sameplace(?:\/|$)/.test(target)) {
          assert.ok(file.startsWith(resolve(root, "frontend/app/portfolio/sameplace") + (process.platform === "win32" ? "\\" : "/")) && target === "@sameplace", `Unexpected SamePlace host import: ${file}`);
        }
      }
    }
  }
}
assert.match(backend, /room_router = make_room_router\(\s*require_sameplace_identity, sameplace_database, sameplace_enabled,?\s*\)/);
assert.match(backend, /app\.include_router\(room_router, prefix="\/api"\)/);
console.log("SamePlace integration boundaries: PASS");
