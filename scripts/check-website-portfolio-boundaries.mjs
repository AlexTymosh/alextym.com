#!/usr/bin/env node

// PR 4: enforce website vs embedded-demo frontend ownership without changing URLs or layout.
// This read-only check uses only Node built-ins; it runs before frontend dependencies install.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const repo = resolve(fileURLToPath(new URL("..", import.meta.url)));
const sourceRoot = join(repo, "portfolio/fleet_hub/frontend/src");
const websiteApp = join(repo, "frontend/app");
const entry = join(sourceRoot, "index.ts");
const hostAdapter = join(websiteApp, "fleet-vor-hub/page.tsx");
const supportedSource = new Set([".js", ".jsx", ".ts", ".tsx", ".mjs"]);
const allowedDependencies = /^(?:react(?:\/.+)?|next(?:\/.+)?)$/;

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((item) => {
    if (item.name === "node_modules" || item.name.startsWith(".")) return [];
    const path = join(directory, item.name);
    // Never follow symlinks, including the local frontend/node_modules junction.
    if (item.isSymbolicLink()) return [];
    return item.isDirectory() ? walk(path) : item.isFile() ? [path] : [];
  });
}

function within(path, directory) {
  const rel = relative(directory, path);
  return rel === "" || (rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel));
}

function importsOf(contents) {
  // Keep static import/export matching anchored to a declaration. The former
  // unanchored matcher could run across a TypeScript union (e.g. "a" | "b")
  // and incorrectly interpret a string literal as a module specifier.
  // Allow multi-line named imports; stop before arbitrary expressions.
  const declarations = /^[ \t]*(?:import|export)[ \t]+(?:type[ \t]+)?[\w*{}, \t\r\n]+?[ \t]+from[ \t]*["']([^"'\r\n]+)["']/gm;
  const sideEffects = /^[ \t]*import[ \t]*["']([^"'\r\n]+)["']/gm;
  const dynamicLiterals = /\b(?:import|require)\s*\(\s*["']([^"'\r\n]+)["']\s*\)/g;
  return [declarations, sideEffects, dynamicLiterals].flatMap(
    (pattern) => [...contents.matchAll(pattern)].map((match) => match[1]),
  );
}

// Regression: a TypeScript union and an unrelated literal must not be treated
// as imported modules (the original PR 4 patch failed on FleetApp.tsx).
assert.deepEqual(
  importsOf([
    'import type { Metadata } from "next";',
    'import { useEffect, type ReactNode } from "react";',
    'type Section = "workspace" | "dashboard";',
    'export type Status = { kind: "ok" | "error" };',
    'const separator = "|";',
    'export { FleetHubApp } from "./FleetApp";',
    'import "./style.module.css";',
    'const imported = import("next/dynamic");',
  ].join("\n")),
  ["next", "react", "./FleetApp", "./style.module.css", "next/dynamic"],
  "Static-import scanner must not match TypeScript union members",
);

function resolvedImport(filename, specifier) {
  const target = resolve(dirname(filename), specifier);
  const candidates = [target, ...[".ts", ".tsx", ".js", ".jsx", ".mjs", ".module.css", ".webp", ".png", ".svg"].map((ext) => `${target}${ext}`), join(target, "index.ts"), join(target, "index.tsx")];
  return candidates.find((p) => existsSync(p));
}

assert.ok(existsSync(entry), "Fleet public frontend entry is missing");
const projectFiles = walk(sourceRoot);
const projectSources = projectFiles.filter((p) => supportedSource.has(extname(p)));
const stylesheets = projectFiles.filter((p) => p.endsWith(".css"));
assert.ok(projectSources.length >= 12, "Fleet implementation appears to be missing");
assert.ok(stylesheets.length >= 10, "Expected Fleet CSS Modules are missing");

for (const file of stylesheets) {
  const name = relative(repo, file);
  assert.ok(file.endsWith(".module.css"), `${name}: global stylesheet is forbidden in Fleet`);
  const css = readFileSync(file, "utf8");
  assert.doesNotMatch(css, /:global\s*(?:\(|\{)/, `${name}: global CSS escape is forbidden`);
  assert.doesNotMatch(css, /@import\b/, `${name}: stylesheet imports must be audited before use`);
  assert.doesNotMatch(css, /(?:^|[{}\n])\s*(?:html|body|:root)\b\s*(?:[,#{.:\s]|\{)/m, `${name}: global document selector is forbidden`);
}

for (const file of projectSources) {
  const name = relative(repo, file);
  const contents = readFileSync(file, "utf8");
  for (const spec of importsOf(contents)) {
    if (!spec.startsWith(".")) {
      assert.match(spec, allowedDependencies, `${name}: unexpected cross-boundary dependency ${spec}`);
      continue;
    }
    const target = resolvedImport(file, spec);
    assert.ok(target, `${name}: missing local import ${spec}`);
    assert.ok(within(target, sourceRoot), `${name}: relative import escapes Fleet ownership: ${spec}`);
    if (target.endsWith(".css")) {
      assert.ok(target.endsWith(".module.css"), `${name}: non-module CSS import ${spec}`);
    }
  }
}

const host = readFileSync(hostAdapter, "utf8");
assert.match(host, /from\s+["']@fleet-hub["']/, "Fleet host page must use its public entry");
assert.match(host, /robots\s*:\s*\{\s*index\s*:\s*false\s*,\s*follow\s*:\s*false/, "Fleet demo must remain noindex/nofollow");
for (const file of walk(websiteApp).filter((p) => supportedSource.has(extname(p)))) {
  const contents = readFileSync(file, "utf8");
  const name = relative(repo, file);
  if (file !== hostAdapter) {
    assert.ok(!importsOf(contents).includes("@fleet-hub"), `${name}: only the Fleet route adapter may import @fleet-hub`);
  }
  assert.doesNotMatch(contents, /(?:from\s*["']|import\s*\(["'])[^"']*portfolio\/fleet_hub\/frontend\/src/, `${name}: direct Fleet internals import`);
}

const rootLayout = readFileSync(join(websiteApp, "layout.tsx"), "utf8");
assert.match(rootLayout, /<SiteNavigation\s*\/>/, "Existing website navigation must remain mounted");
assert.match(rootLayout, /className="site-main"/, "Existing website shell must remain unchanged");
assert.match(rootLayout, /className="site-footer site-footer--with-disclaimer"/, "Footer contract changed");
const globalCss = readFileSync(join(websiteApp, "globals.css"), "utf8");
assert.doesNotMatch(globalCss, /\.(?:fleet[-_]?hub|vor[-_]?hub)(?:\b|[_-])/i, "Website stylesheet must not target Fleet domain classes");
const hostRoute = join(websiteApp, "fleet-vor-hub");
for (const subroute of ["register", "new-defect", "process"]) {
  const file = join(hostRoute, subroute, "page.tsx");
  assert.match(readFileSync(file, "utf8"), /redirect\(["']\/fleet-vor-hub["']\)/, `${subroute}: public redirect changed`);
}
const siteConfig = readFileSync(join(repo, "frontend/lib/site-config.ts"), "utf8");
assert.doesNotMatch(siteConfig, /href:\s*["']\/portfolio["']/, "Unpublished portfolio navigation was exposed");
console.log(`Website/Portfolio boundaries: PASS (${projectSources.length} project sources, ${stylesheets.length} scoped CSS Modules, four preserved host routes)`);
