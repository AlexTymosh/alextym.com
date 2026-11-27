import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { after, test } from "node:test";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const source = resolve(root, "portfolio/sameplace/frontend/src/i18n");
const requireFromHost = createRequire(resolve(root, "frontend/package.json"));
const out = mkdtempSync(join(tmpdir(), "sameplace-i18n-"));
after(() => rmSync(out, { recursive: true, force: true }));
// Compile the actual production translator, not a reimplementation of it.
const tsc = process.env.SAMEPLACE_TEST_TSC || requireFromHost.resolve("typescript/bin/tsc");
execFileSync(process.execPath, [tsc, "--strict", "--target", "ES2020", "--module", "commonjs",
  "--resolveJsonModule", "--esModuleInterop", "--skipLibCheck", "--outDir", out,
  resolve(source, "messages.ts")], { stdio: "inherit" });
const requireCompiled = createRequire(join(out, "entry.cjs"));
const { createTranslator, resolveLocale, playerCount, SUPPORTED_LOCALES } = requireCompiled("./messages.js");
const raw = readFileSync(resolve(source, "messages.ru.json"), "utf8");
const ru = JSON.parse(raw);
const placeholders = (value) => [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g)].map((m) => m[1]).sort();

test("Russian is the only enabled locale and fallback is deterministic", () => {
  assert.deepEqual(SUPPORTED_LOCALES, ["ru"]);
  for (const language of ["ru-RU", "RU", "en", "uk-UA", undefined, ""]) assert.equal(resolveLocale(language), "ru");
  assert.equal(createTranslator("en")("foundation.motto"), ru["foundation.motto"]);
});
test("translation keys are unique, complete and nonempty", () => {
  const keys = [...raw.matchAll(/^\s*"([^"\r\n]+)"\s*:/gm)].map((m) => m[1]);
  assert.equal(new Set(keys).size, keys.length);
  assert.deepEqual(keys.sort(), Object.keys(ru).sort());
  for (const key of ["foundation.stage", "foundation.motto", "foundation.description", "foundation.notice", "fallback.missing", "players.one", "players.few", "players.many", "players.other"]) {
    assert.ok(typeof ru[key] === "string" && ru[key].trim());
  }
  for (const key of ["players.one", "players.few", "players.many", "players.other"]) assert.deepEqual(placeholders(ru[key]), ["count"]);
});
test("Russian plural rules use all relevant categories", () => {
  for (const [n, key] of [[0,"many"],[1,"one"],[2,"few"],[5,"many"],[11,"many"],[21,"one"],[22,"few"],[25,"many"]]) {
    assert.equal(playerCount(n), ru[`players.${key}`].replace("{count}", String(n)));
  }
  assert.throws(() => playerCount(-1), RangeError);
});
test("missing keys and parameters fail safely without exposing machine errors", () => {
  assert.equal(createTranslator("ru")("unknown.key"), ru["fallback.missing"]);
  assert.equal(createTranslator("ru")("players.one"), ru["fallback.missing"]);
  assert.throws(() => createTranslator("ru", { strict: true })("unknown.key"));
  assert.throws(() => createTranslator("ru", { strict: true })("players.one"));
});
test("pseudo translation stretches labels without changing identifiers or the default dictionary", () => {
  const pseudo = Object.fromEntries(Object.entries(ru).map(([k, v]) => [k, `[${v} ${v.replace(/\{[^}]+\}/g, "")}]`]));
  for (const k of Object.keys(ru)) assert.deepEqual(placeholders(pseudo[k]), placeholders(ru[k]));
  const t = createTranslator("ru", { strict: true, dictionary: pseudo });
  assert.ok(t("foundation.motto").length > ru["foundation.motto"].length);
  assert.ok(t("players.one", { count: 1 }).includes("1"));
  assert.equal(createTranslator("ru")("foundation.motto"), ru["foundation.motto"]);
});
