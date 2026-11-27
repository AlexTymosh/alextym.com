#!/usr/bin/env node
// Reuse the host ESLint installation; resolve the lint base from the owned module.
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const frontend = resolve(root, "frontend");
const result = spawnSync(process.execPath, [
  resolve(frontend, "node_modules/eslint/bin/eslint.js"), "--config",
  resolve(frontend, "eslint.config.mjs"), "src",
], { cwd: resolve(root, "portfolio/sameplace/frontend"), stdio: "inherit", shell: false });
if (result.error) console.error(result.error.message);
process.exitCode = result.status ?? 1;
