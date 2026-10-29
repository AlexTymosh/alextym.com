#!/usr/bin/env node

// Make the host's single npm installation available to the embedded Fleet UI.
// Link inside the Fleet project, not at the repository root: root node_modules
// may already be a real directory owned by other tooling and must be left alone.
import { lstatSync, realpathSync, symlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDir, "..");
const repoRoot = resolve(frontendRoot, "..");
const moduleRoot = join(repoRoot, "portfolio", "fleet_hub", "frontend");
const target = join(frontendRoot, "node_modules");
const link = join(moduleRoot, "node_modules");

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

const existing = statOrNull(link);
if (existing) {
  if (!existing.isSymbolicLink()) {
    console.error("Fleet frontend node_modules exists as a real directory; refusing to change it.");
    process.exit(1);
  }
  if (realpathSync(link) !== realpathSync(target)) {
    console.error("Fleet frontend node_modules link points elsewhere; refusing to change it.");
    process.exit(1);
  }
  console.log("Fleet frontend dependency link: OK");
} else {
  symlinkSync(target, link, process.platform === "win32" ? "junction" : "dir");
  console.log("Fleet frontend dependency link: created (ignored by Git)");
}
