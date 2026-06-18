import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const sourcePath = resolve(repoRoot, "config", "project.config.json");
const targetDir = resolve(frontendRoot, ".generated");
const targetPath = resolve(targetDir, "project.config.json");

JSON.parse(readFileSync(sourcePath, "utf8"));
mkdirSync(targetDir, { recursive: true });
copyFileSync(sourcePath, targetPath);

console.log("Synced shared project config for frontend.");
