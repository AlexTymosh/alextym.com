#!/usr/bin/env node
// Post-migration hygiene contract. Does not execute migration tools or touch DBs.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const scripts = join(root, "scripts");
const removedPatterns = [
  /^apply_vor_.*\.py$/,
  /^check_vor_.*\.py$/,
  /^install_vor_hub\.py$/,
  /^repair_vor_ui_entry\.py$/,
];
const survivors = readdirSync(scripts).filter((name) =>
  removedPatterns.some((pattern) => pattern.test(name)),
);
assert.deepEqual(survivors, [], `Obsolete one-shot Fleet migration scripts remain: ${survivors.join(", ")}`);

for (const name of [
  "backup_vor_v2.py",
  "configure-vor-subscribers.ps1",
  "start-vor-backend.ps1",
  "start-vor-frontend.ps1",
]) {
  assert.ok(existsSync(join(scripts, name)), `Preserved Fleet utility missing: ${name}`);
}

const task = readFileSync(join(root, "Taskfile.yml"), "utf8");
assert.match(task, /node scripts\/check-fleet-legacy-tooling\.mjs/);
const notes = readFileSync(join(root, "SESSION_NOTES.md"), "utf8");
assert.match(notes, /^# Current handoff — PR 5: final portfolio architecture audit/m);
const test = readFileSync(join(root, "frontend/e2e/fleet-hub-authenticated.spec.ts"), "utf8");
assert.match(test, /mockAuthenticatedFleet/);
assert.match(test, /POST \/api\/vor\/logout/);

console.log("Fleet legacy-tooling audit: PASS (obsolete patch scripts removed; live utilities preserved)");
