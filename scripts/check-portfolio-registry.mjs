#!/usr/bin/env node

// Validate registered portfolio modules; publication is a separate product decision.
// This is deliberately a read-only, dependency-free check for the existing CI job.

import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const portfolio = join(root, "portfolio");
const errors = [];

function fail(message) {
  errors.push(message);
}

function loadJson(relativePath) {
  const absolute = join(root, relativePath);
  try {
    return JSON.parse(readFileSync(absolute, "utf8"));
  } catch (error) {
    fail(`${relativePath}: ${error.message}`);
    return null;
  }
}

function requireFile(relativePath) {
  if (!existsSync(join(root, relativePath))) {
    fail(`Missing ${relativePath}`);
  }
}

function requireNonEmptyString(value, name) {
  if (typeof value !== "string" || !value.trim()) {
    fail(`${name} must be a nonempty string`);
  }
}

function validLocalRoute(path) {
  return typeof path === "string" && /^\/(?!\/)[a-z0-9/-]+$/.test(path) &&
    !path.includes("..") && !path.endsWith("/");
}

requireFile("portfolio/README.md");
requireFile("docs/architecture/portfolio.md");

const registry = loadJson("portfolio/catalog/registry.json");
const ids = registry?.projectIds;
if (registry?.schemaVersion !== 1) {
  fail("portfolio/catalog/registry.json: schemaVersion must equal 1");
}
if (!Array.isArray(ids) || ids.length === 0) {
  fail("portfolio/catalog/registry.json: projectIds must be a nonempty array");
}

const expectedIds = Array.isArray(ids) ? ids : [];
const idSet = new Set();
const demoPathSet = new Set();
const apiPathSet = new Set();

for (const id of expectedIds) {
  if (typeof id !== "string" || !/^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/.test(id)) {
    fail(`Invalid project id: ${String(id)}`);
    continue;
  }
  if (idSet.has(id)) {
    fail(`Duplicate project id: ${id}`);
    continue;
  }
  idSet.add(id);

  const prefix = `portfolio/${id}`;
  const metadata = loadJson(`${prefix}/project.json`);
  requireFile(`${prefix}/README.md`);
  for (const folder of ["frontend", "backend", "tests"]) {
    requireFile(`${prefix}/${folder}/README.md`);
  }
  if (metadata === null) {
    continue;
  }
  if (metadata.schemaVersion !== 1 || metadata.id !== id) {
    fail(`${prefix}/project.json: schemaVersion or id mismatch`);
  }
  if (metadata.mode !== "embedded") {
    fail(`${prefix}/project.json: mode must be embedded`);
  }
  if (typeof metadata.slug !== "string" ||
      !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(metadata.slug)) {
    fail(`${prefix}/project.json: invalid slug`);
  }
  for (const field of ["title", "summary", "category"]) {
    requireNonEmptyString(metadata[field], `${prefix}/project.json.${field}`);
  }
  if (!Array.isArray(metadata.technologies) || metadata.technologies.length === 0 ||
      !metadata.technologies.every(item => typeof item === "string" && item.trim())) {
    fail(`${prefix}/project.json: technologies must contain nonempty strings`);
  }
  const demoPath = metadata.demo?.path;
  const apiPrefix = metadata.demo?.apiPrefix;
  if (!validLocalRoute(demoPath)) {
    fail(`${prefix}/project.json: invalid demo.path`);
  } else {
    if (demoPathSet.has(demoPath)) fail(`Duplicate demo route: ${demoPath}`);
    demoPathSet.add(demoPath);
    requireFile(`frontend/app${demoPath}/page.tsx`);
  }
  if (!validLocalRoute(apiPrefix) || !apiPrefix.startsWith("/api/")) {
    fail(`${prefix}/project.json: invalid demo.apiPrefix`);
  } else {
    if (apiPathSet.has(apiPrefix)) fail(`Duplicate apiPrefix: ${apiPrefix}`);
    apiPathSet.add(apiPrefix);
  }
}

// Detect forgotten or unregistered portfolio project directories.
if (existsSync(portfolio)) {
  for (const entry of readdirSync(portfolio)) {
    if (entry === "catalog") continue;
    const full = join(portfolio, entry);
    if (statSync(full).isDirectory() && !idSet.has(entry)) {
      fail(`Unregistered project directory: portfolio/${entry}`);
    }
  }
}

// Publication policy belongs to the website and is checked separately.

if (errors.length) {
  console.error("Portfolio registry check failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exitCode = 1;
} else {
  assert.equal(expectedIds.length, idSet.size);
  console.log(`Portfolio registry check passed (${idSet.size} registered project(s)).`);
}
