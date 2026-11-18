import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
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

const registry = JSON.parse(readFileSync(resolve(repoRoot, "portfolio/catalog/registry.json"), "utf8"));
const projects = registry.projectIds.map((id) => {
  if (!/^[a-z][a-z0-9_]*$/.test(id)) throw new Error("Invalid portfolio project ID");
  const manifest = JSON.parse(readFileSync(resolve(repoRoot, "portfolio", id, "project.json"), "utf8"));
  if (manifest.id !== id || !manifest.demo.path.startsWith("/") || manifest.demo.path.startsWith("//")) {
    throw new Error("Invalid portfolio project manifest");
  }
  return { id, title: manifest.title, summary: manifest.summary, path: manifest.demo.path };
});
writeFileSync(resolve(targetDir, "portfolio-projects.json"), JSON.stringify(projects, null, 2) + "\n");

console.log("Synced shared project config for frontend.");
