#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { basename, resolve } from "node:path";

const rawCyrillicPattern = /[\u0400-\u04ff]/u;
const maxReportedMatches = 50;

const trackedFiles = execFileSync("git", ["ls-files", "-z"], {
  encoding: "buffer",
})
  .toString("utf8")
  .split("\0")
  .filter(Boolean);

const failures = [];

for (const relativePath of trackedFiles) {
  if (isAllowedRussianDocument(relativePath)) {
    continue;
  }

  const fileBuffer = readFileSync(resolve(relativePath));
  if (fileBuffer.includes(0)) {
    continue;
  }

  const fileText = fileBuffer.toString("utf8");
  if (!rawCyrillicPattern.test(fileText)) {
    continue;
  }

  const lineNumber = firstMatchingLineNumber(fileText);
  failures.push(`${relativePath}:${lineNumber}: contains raw Cyrillic characters`);
}

if (failures.length > 0) {
  console.error("Raw Cyrillic check failed:");
  for (const failure of failures.slice(0, maxReportedMatches)) {
    console.error(`- ${failure}`);
  }
  if (failures.length > maxReportedMatches) {
    console.error(`- ...and ${failures.length - maxReportedMatches} more`);
  }
  console.error("Use escaped Unicode strings or Russian documentation files marked with .ru.");
  process.exit(1);
}

console.log("Raw Cyrillic check passed.");

function isAllowedRussianDocument(relativePath) {
  const fileName = basename(relativePath).toLowerCase();
  return fileName.includes(".ru.") || fileName.endsWith(".ru");
}

function firstMatchingLineNumber(fileText) {
  const lines = fileText.split(/\r?\n/u);
  const index = lines.findIndex((line) => rawCyrillicPattern.test(line));
  return index === -1 ? 1 : index + 1;
}
