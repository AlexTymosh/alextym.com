import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync, renameSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { test } from "node:test";
import { inventory, verifyFreeze, protectedPath } from "./check-freeze.mjs";

function fixture(t) {
  const repo = mkdtempSync(join(tmpdir(), "sameplace-freeze-"));
  t.after(() => rmSync(repo, { recursive: true, force: true }));
  const git = (...args) => execFileSync("git", args, { cwd: repo, encoding: "utf8" }).trim();
  const write = (file, data) => { mkdirSync(dirname(join(repo, file)), { recursive: true }); writeFileSync(join(repo, file), data); };
  git("init", "-q"); git("config", "user.name", "Fixture"); git("config", "user.email", "fixture@example.invalid");
  git("config", "core.autocrlf", "false");
  write("portfolio/preferans/game.py", "original\n");
  write("frontend/components/preferans-site-bar.tsx", "legacy\n");
  write("frontend/app/page.tsx", "host\n");
  git("add", "."); git("commit", "-qm", "fixture");
  const baseline = git("rev-parse", "HEAD");
  const manifest = { schema_version: 1, baseline, files: inventory(repo, baseline) };
  return { repo, git, write, baseline, manifest, verify: () => verifyFreeze(repo, baseline, manifest) };
}

test("unchanged legacy and new SamePlace engine are allowed", (t) => {
  const f = fixture(t);
  f.write("portfolio/sameplace/backend/src/sameplace/preferans_engine.py", "new\n");
  f.write("frontend/app/page.tsx", "host updated\n");
  assert.equal(f.verify(), 2);
  assert.equal(protectedPath("frontend/e2e/preferans-pr42.ru.spec.ts"), true);
});
for (const [name, mutate] of [
  ["unstaged edit", (f) => f.write("portfolio/preferans/game.py", "changed\n")],
  ["staged edit", (f) => { f.write("portfolio/preferans/game.py", "changed\n"); f.git("add", "portfolio/preferans/game.py"); }],
  ["deleted", (f) => rmSync(join(f.repo, "portfolio/preferans/game.py"))],
  ["untracked addition", (f) => f.write("portfolio/preferans/new.py", "new\n")],
  ["staged addition", (f) => { f.write("portfolio/preferans/new.py", "new\n"); f.git("add", "portfolio/preferans/new.py"); }],
  ["renamed", (f) => renameSync(join(f.repo, "portfolio/preferans/game.py"), join(f.repo, "portfolio/preferans/renamed.py"))],
  ["mode changed", (f) => f.git("update-index", "--chmod=+x", "portfolio/preferans/game.py")],
  ["host adapter edit", (f) => f.write("frontend/components/preferans-site-bar.tsx", "changed\n")],
  ["manifest tampering", (f) => f.manifest.files.pop()],
  ["assume unchanged", (f) => f.git("update-index", "--assume-unchanged", "portfolio/preferans/game.py")],
]) {
  test(`freeze rejects ${name}`, (t) => { const f = fixture(t); mutate(f); assert.throws(f.verify); });
}
