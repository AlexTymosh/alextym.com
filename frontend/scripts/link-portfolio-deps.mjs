#!/usr/bin/env node

// Share the host's single npm install with all registered embedded frontends.
// Do not create or replace a real node_modules directory inside a project.
import { lstatSync, readFileSync, realpathSync, symlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDir, "..");
const repoRoot = resolve(frontendRoot, "..");
const target = join(frontendRoot, "node_modules");
const registry = JSON.parse(readFileSync(join(repoRoot, "portfolio/catalog/registry.json"), "utf8"));

function statOrNull(path) {
  try {
    return lstatSync(path);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

if (!statOrNull(target)?.isDirectory()) {
  console.error("Missing frontend/node_modules: run npm ci from frontend/ first.");
  process.exit(1);
}

if (registry.schemaVersion !== 1 || !Array.isArray(registry.projectIds)) {
  throw new Error("Invalid portfolio registry");
}

for (const id of registry.projectIds) {
  if (typeof id !== "string" || !/^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/.test(id)) {
    throw new Error("Invalid portfolio project ID");
  }
  const link = join(repoRoot, "portfolio", id, "frontend", "node_modules");
  const existing = statOrNull(link);
  if (existing) {
    if (!existing.isSymbolicLink()) {
      throw new Error(`${id}: frontend node_modules is a real directory; refusing to change it`);
    }
    if (realpathSync(link) !== realpathSync(target)) {
      throw new Error(`${id}: frontend node_modules link points elsewhere; refusing to change it`);
    }
    console.log(`${id}: frontend dependency link OK`);
  } else {
    symlinkSync(target, link, process.platform === "win32" ? "junction" : "dir");
    console.log(`${id}: frontend dependency link created (ignored by Git)`);
  }
}
