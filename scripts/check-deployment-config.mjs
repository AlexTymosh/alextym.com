#!/usr/bin/env node

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const repoRoot = process.cwd();
const vercelConfigPath = resolve(repoRoot, "frontend", "vercel.json");
const nextConfigPath = resolve(repoRoot, "frontend", "next.config.mjs");

const vercelConfig = JSON.parse(readFileSync(vercelConfigPath, "utf8"));
assert.equal(
  Object.hasOwn(vercelConfig, "rewrites"),
  false,
  "frontend/vercel.json must not hardcode /api rewrites; use BACKEND_ORIGIN in next.config.mjs.",
);

const previousBackendOrigin = process.env.BACKEND_ORIGIN;
const previousVercel = process.env.VERCEL;

try {
  const moduleUrl = `${pathToFileURL(nextConfigPath).href}?check=${Date.now()}`;
  const { default: nextConfig } = await import(moduleUrl);
  assert.equal(typeof nextConfig.rewrites, "function", "next.config.mjs must define rewrites().");

  delete process.env.BACKEND_ORIGIN;
  delete process.env.VERCEL;
  assert.deepEqual(
    await nextConfig.rewrites(),
    [],
    "Local builds without BACKEND_ORIGIN should not create rewrites.",
  );

  process.env.BACKEND_ORIGIN = "https://backend.example.com/";
  assert.deepEqual(await nextConfig.rewrites(), [
    {
      source: "/api/:path*",
      destination: "https://backend.example.com/api/:path*",
    },
  ]);

  delete process.env.BACKEND_ORIGIN;
  process.env.VERCEL = "1";
  await assert.rejects(
    () => nextConfig.rewrites(),
    /BACKEND_ORIGIN is required/,
    "Vercel deployments must fail fast when BACKEND_ORIGIN is missing.",
  );
} finally {
  restoreEnv("BACKEND_ORIGIN", previousBackendOrigin);
  restoreEnv("VERCEL", previousVercel);
}

console.log("Deployment config check passed.");

function restoreEnv(name, value) {
  if (value === undefined) {
    delete process.env[name];
    return;
  }
  process.env[name] = value;
}
