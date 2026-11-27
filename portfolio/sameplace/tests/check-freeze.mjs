#!/usr/bin/env node
// Compare the immutable Git tree, checked-in inventory, index and working tree.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const BASELINE = "1e76eaa4c0ba58ceed0e5b5615917a6ee229f777";
const root = fileURLToPath(new URL("../../../", import.meta.url));
const inventoryPath = "portfolio/sameplace/docs/legacy-freeze.json";

export function protectedPath(path) {
  // Includes all legacy-only named adapters, assets, tests and scripts outside SamePlace.
  // Shared host files are covered by integration checks, not blanket freezing.
  return !path.startsWith("portfolio/sameplace/") && /preferans/i.test(path);
}

function git(repo, args) {
  return execFileSync("git", args, { cwd: repo, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}
function entries(output, tree) {
  return output.split("\0").filter(Boolean).map((line) => {
    const split = line.indexOf("\t");
    assert.ok(split >= 0, "Invalid Git entry");
    const path = line.slice(split + 1);
    const fields = line.slice(0, split).split(" ");
    if (!tree) assert.equal(fields[2], "0", `Unmerged index entry: ${path}`);
    return { path, mode: fields[0], oid: fields[tree ? 2 : 1] };
  }).filter((entry) => protectedPath(entry.path)).sort((a, b) => Buffer.compare(Buffer.from(a.path), Buffer.from(b.path)));
}

export function inventory(repo, baseline) {
  return entries(git(repo, ["ls-tree", "-r", "-z", baseline]), true);
}

export function verifyFreeze(repo, baseline, manifest) {
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.baseline, baseline, "Frozen baseline changed");
  const expected = inventory(repo, baseline);
  assert.ok(expected.some((entry) => entry.path.startsWith("portfolio/preferans/")), "Missing legacy project");
  assert.deepEqual(manifest.files, expected, "Freeze inventory differs from the immutable Git tree");
  const current = entries(git(repo, ["ls-files", "--stage", "-z"]), false);
  assert.deepEqual(current, expected, "Protected index content, mode or path differs from baseline");
  // Ignore Git's rename heuristic; both sides of a rename must be considered.
  const changed = git(repo, ["diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", baseline, "--"])
    .split("\0").filter(protectedPath);
  assert.deepEqual(changed, [], "Protected working-tree files changed");
  const untracked = git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    .split("\0").filter(protectedPath);
  assert.deepEqual(untracked, [], "New protected working-tree files");
  // A skip-worktree/assume-unchanged flag can hide a working-tree change from Git diff.
  const hidden = git(repo, ["ls-files", "-v", "-z"]).split("\0")
    .filter((line) => line && protectedPath(line.slice(2)) && line[0] !== "H");
  assert.deepEqual(hidden, [], "Protected paths must not hide local modifications");
  return expected.length;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const manifest = JSON.parse(readFileSync(resolve(root, inventoryPath), "utf8"));
    const count = verifyFreeze(root, BASELINE, manifest);
    console.log(`Legacy Preferans freeze: PASS (${count} protected Git blobs)`);
  } catch (error) {
    console.error(`Legacy Preferans freeze: FAIL: ${error.message}`);
    process.exitCode = 1;
  }
}
