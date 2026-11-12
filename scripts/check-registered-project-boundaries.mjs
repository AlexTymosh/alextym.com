#!/usr/bin/env node
// Read-only contract for ALL registered project frontends. A static guard, not a sandbox.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const registered = JSON.parse(readFileSync(join(root, "portfolio/catalog/registry.json"), "utf8"));
assert.equal(registered.schemaVersion, 1);
assert.ok(Array.isArray(registered.projectIds) && registered.projectIds.length > 0);
const sourceExtensions = new Set([".js", ".jsx", ".mjs", ".ts", ".tsx"]);
const importRegexes = [
  /^[ \t]*(?:import|export)[ \t]+(?:type[ \t]+)?[\w*{}, \t\r\n]+?[ \t]+from[ \t]*["']([^"'\r\n]+)["']/gm,
  /^[ \t]*import[ \t]*["']([^"'\r\n]+)["']/gm,
  /\b(?:import|require)\s*\(\s*["']([^"'\r\n]+)["']\s*\)/g,
];
const importsOf = (content) => importRegexes.flatMap((regex) => [...content.matchAll(regex)].map((match) => match[1]));

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((item) => {
    if (item.isSymbolicLink() || item.name === "node_modules" || item.name.startsWith(".")) return [];
    const path = join(dir, item.name);
    return item.isDirectory() ? walk(path) : item.isFile() ? [path] : [];
  });
}
function isWithin(path, directory) {
  const rel = relative(directory, path);
  return rel === "" || (rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel));
}
function resolveLocal(path, specifier) {
  const base = resolve(dirname(path), specifier);
  const candidates = [base, ...[".ts", ".tsx", ".js", ".jsx", ".mjs", ".module.css", ".svg", ".png", ".webp"]
    .map((ext) => base + ext), join(base, "index.ts"), join(base, "index.tsx")];
  return candidates.find((candidate) => existsSync(candidate));
}

for (const id of registered.projectIds) {
  assert.match(id, /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/);
  const sourceRoot = join(root, "portfolio", id, "frontend/src");
  assert.ok(existsSync(sourceRoot), id + ": missing frontend/src");
  const all = walk(sourceRoot);
  const sources = all.filter((file) => sourceExtensions.has(extname(file)));
  assert.ok(sources.length > 0, id + ": no source modules");
  for (const path of sources) {
    const name = relative(root, path);
    for (const specifier of importsOf(readFileSync(path, "utf8"))) {
      if (specifier.startsWith(".")) {
        const resolved = resolveLocal(path, specifier);
        assert.ok(resolved, name + ": unresolved local import " + specifier);
        assert.ok(isWithin(resolved, sourceRoot), name + ": escaped project frontend: " + specifier);
      } else {
        assert.doesNotMatch(specifier, /^(?:portfolio\/|frontend\/|backend\/|@portfolio\/)/,
          name + ": direct cross-boundary import " + specifier);
      }
    }
  }
  for (const cssPath of all.filter((path) => path.endsWith(".css"))) {
    const name = relative(root, cssPath);
    assert.ok(cssPath.endsWith(".module.css"), name + ": global CSS forbidden");
    const css = readFileSync(cssPath, "utf8");
    assert.doesNotMatch(css, /:global\s*(?:\(|\{)/, name + ": global CSS escape forbidden");
    assert.doesNotMatch(css, /@import\b/, name + ": CSS import requires review");
  }
}
console.log(`Registered frontend project boundaries: PASS (${registered.projectIds.length} projects)`);
