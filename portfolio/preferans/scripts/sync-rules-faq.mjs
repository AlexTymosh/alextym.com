import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const read = (name) => readFileSync(new URL(`../docs/${name}`, import.meta.url), "utf8").replace(/\r\n/g, "\n");
const destination = fileURLToPath(new URL("../frontend/src/rules-source.ru.json", import.meta.url));
const expected = JSON.stringify({rules:read("HOUSE_RULES.ru.md"), decisions:read("HOUSE_RULES_DECISIONS.ru.md")}, null, 2) + "\n";
if (process.argv.includes("--check")) {
  if (readFileSync(destination, "utf8").replace(/\r\n/g, "\n") !== expected) {
    console.error("FAQ snapshot is stale. Run node portfolio/preferans/scripts/sync-rules-faq.mjs");
    process.exitCode = 1;
  }
} else {
  writeFileSync(destination, expected, "utf8");
  console.log("FAQ snapshot updated from authoritative documents.");
}
