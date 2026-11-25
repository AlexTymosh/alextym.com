import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const checker = fileURLToPath(new URL("./check-no-raw-cyrillic.mjs", import.meta.url));
const russianText = "\u041f\u0440\u0438\u0432\u0435\u0442 \u0401\u0451";

function repository(t) {
  const cwd = mkdtempSync(join(tmpdir(), "raw-cyrillic-test-"));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  function git(...args) {
    return execFileSync("git", args, { cwd, encoding: "utf8" });
  }
  git("init", "--quiet");
  function write(path, content) {
    const target = join(cwd, path);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, content);
  }
  function check() {
    const result = spawnSync(process.execPath, [checker], { cwd, encoding: "utf8" });
    assert.ifError(result.error);
    assert.equal(result.signal, null);
    return result;
  }
  return { cwd, git, write, check };
}

function expectFailure(repo, path, line) {
  const result = repo.check();
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.ok(
    result.stderr.includes(`${path}:${line}: contains raw Cyrillic characters`),
    result.stderr,
  );
}

function expectSuccess(repo) {
  const result = repo.check();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /Raw Cyrillic check passed/);
}

test("rejects raw Cyrillic in a new untracked source before git add", (t) => {
  const repo = repository(t);
  const path = "portfolio/example with spaces/ruleset.py";
  repo.write(path, `# English\nname = "${russianText}"\n`);
  assert.equal(repo.git("ls-files", "--cached"), "");
  expectFailure(repo, path, 2);
});

test("rejects a staged new source", (t) => {
  const repo = repository(t);
  repo.write("ruleset.py", russianText);
  repo.git("add", "--", "ruleset.py");
  expectFailure(repo, "ruleset.py", 1);
});

test("rejects a tracked source modified after staging", (t) => {
  const repo = repository(t);
  repo.write("ruleset.py", "English\n");
  repo.git("add", "--", "ruleset.py");
  repo.write("ruleset.py", `English\n${russianText}\n`);
  expectFailure(repo, "ruleset.py", 2);
});

test("accepts Unicode escapes and ordinary English source", (t) => {
  const repo = repository(t);
  repo.write("ruleset.py", String.raw`name = "\u041f\u0440\u0438\u0432\u0435\u0442"`);
  repo.write("AGENTS.md", "Use Unicode escapes.");
  expectSuccess(repo);
});

test("preserves localized filename exemptions for tracked and new files", (t) => {
  const repo = repository(t);
  repo.write("docs/rules.ru.md", russianText);
  repo.git("add", "--", "docs/rules.ru.md");
  repo.write("frontend/Controls.ru.tsx", russianText);
  repo.write("locale.RU", russianText);
  expectSuccess(repo);
  repo.write("docs.ru/not-localized.md", russianText);
  expectFailure(repo, "docs.ru/not-localized.md", 1);
});

test("ignores new files excluded by Git ignore rules", (t) => {
  const repo = repository(t);
  repo.write(".gitignore", "private/\nnode_modules/\n.env\n");
  repo.write("private/draft.md", russianText);
  repo.write("node_modules/example/index.js", russianText);
  repo.write(".env", russianText);
  expectSuccess(repo);
});

test("still checks tracked files even when their path is ignored", (t) => {
  const repo = repository(t);
  repo.write(".gitignore", "ignored.py\n");
  repo.write("ignored.py", russianText);
  repo.git("add", "--force", "--", "ignored.py");
  expectFailure(repo, "ignored.py", 1);
});

test("preserves handling of deleted tracked files and binary data", (t) => {
  const repo = repository(t);
  repo.write("deleted.py", russianText);
  repo.git("add", "--", "deleted.py");
  rmSync(join(repo.cwd, "deleted.py"));
  repo.write("asset.bin", Buffer.concat([Buffer.from([0]), Buffer.from(russianText)]));
  expectSuccess(repo);
});
