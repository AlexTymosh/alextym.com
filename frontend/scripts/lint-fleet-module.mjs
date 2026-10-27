#!/usr/bin/env node

// ESLint 9 resolves its file base from the working directory. The Fleet Hub
// source is a sibling of frontend/, so lint it from its own module root using
// the host's existing Next.js ESLint configuration and dependency installation.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const fleetRoot = resolve(frontendRoot, "..", "portfolio", "fleet_hub", "frontend");
const eslintCli = join(frontendRoot, "node_modules", "eslint", "bin", "eslint.js");
const eslintConfig = join(frontendRoot, "eslint.config.mjs");
const fleetEntrypoint = join(fleetRoot, "src", "index.ts");

for (const [file, hint] of [
  [eslintCli, "Run npm ci from frontend/ first."],
  [eslintConfig, "The host ESLint configuration is missing."],
  [fleetEntrypoint, "The Fleet Hub frontend module is missing."],
]) {
  if (!existsSync(file)) {
    console.error(`Fleet frontend lint: missing ${file}. ${hint}`);
    process.exit(1);
  }
}

console.log("Linting portfolio/fleet_hub/frontend/src with the host Next.js rules...");
const result = spawnSync(
  process.execPath,
  [eslintCli, "--config", eslintConfig, "src"],
  { cwd: fleetRoot, stdio: "inherit", shell: false },
);
if (result.error) {
  console.error(`Fleet frontend lint could not start: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
