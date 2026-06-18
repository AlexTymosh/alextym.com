#!/usr/bin/env node

import { spawn } from "node:child_process";

const allChecks = [
  { name: "Repository hygiene", task: "repo:check" },
  { name: "Project config", task: "config:check" },
  { name: "Setup wizard", task: "wizard:check" },
  { name: "Deployment config", task: "deployment:check" },
  { name: "Backend", task: "backend:check" },
  { name: "Frontend", task: "frontend:check" },
  { name: "Free RAG", task: "rag:check" },
  { name: "Docker build", task: "docker:build" },
];
const selectedTasks = parseSelectedTasks(process.env.CI_CHECKS);
const checks =
  selectedTasks.length === 0
    ? allChecks
    : allChecks.filter((check) => selectedTasks.includes(check.task));
const taskExecutable = process.env.TASK_COMMAND || "task";

if (selectedTasks.length > 0 && checks.length !== selectedTasks.length) {
  const availableTasks = allChecks.map((check) => check.task).join(", ");
  console.error(`Unknown CI_CHECKS value. Available tasks: ${availableTasks}`);
  process.exit(1);
}

const useColour = !process.env.NO_COLOR;
const colour = {
  bold: useColour ? "\x1b[1m" : "",
  green: useColour ? "\x1b[32m" : "",
  red: useColour ? "\x1b[31m" : "",
  yellow: useColour ? "\x1b[33m" : "",
  reset: useColour ? "\x1b[0m" : "",
};

const results = [];

for (const check of checks) {
  printSection(`Running ${check.name}`);
  const startedAt = Date.now();
  const result = await runTask(check.task);
  const durationMs = Date.now() - startedAt;
  const status = result.status ?? 1;
  const passed = status === 0 && !result.error;

  results.push({
    ...check,
    durationMs,
    error: result.error,
    passed,
    signal: result.signal,
    status,
  });
}

printSummary(results);

if (results.some((result) => !result.passed)) {
  process.exit(1);
}

function printSection(title) {
  console.log("");
  console.log(`${colour.bold}${title}${colour.reset}`);
  console.log("-".repeat(title.length));
}

function printSummary(summaryResults) {
  const failedResults = summaryResults.filter((result) => !result.passed);

  console.log("");
  console.log("=================================================================");
  console.log(`${colour.bold}\`task ci\` summary:${colour.reset}`);
  console.log("");

  for (const result of summaryResults) {
    const statusText = result.passed
      ? `${colour.green}[PASS]${colour.reset}`
      : `${colour.red}[FAIL]${colour.reset}`;
    const duration = formatDuration(result.durationMs);
    const failureDetail = formatFailureDetail(result);
    console.log(`${statusText} ${result.name} (${duration})${failureDetail}`);
  }

  console.log("");
  if (failedResults.length === 0) {
    console.log(`${colour.green}All free CI checks passed.${colour.reset}`);
    return;
  }

  const plural = failedResults.length === 1 ? "check" : "checks";
  console.log(
    `${colour.red}CI failed: ${failedResults.length} ${plural} failed.${colour.reset}`,
  );
}

function runTask(taskName) {
  return new Promise((resolve) => {
    let isSettled = false;
    const child = spawn(taskExecutable, ["--silent", taskName], {
      env: { ...process.env, FORCE_COLOR: process.env.FORCE_COLOR || "1" },
    });

    child.stdout.on("data", (data) => {
      process.stdout.write(data);
    });
    child.stderr.on("data", (data) => {
      process.stdout.write(data);
    });
    child.on("error", (error) => {
      if (isSettled) {
        return;
      }
      isSettled = true;
      resolve({ error, signal: null, status: 1 });
    });
    child.on("close", (status, signal) => {
      if (isSettled) {
        return;
      }
      isSettled = true;
      resolve({ error: null, signal, status });
    });
  });
}

function formatDuration(durationMs) {
  const seconds = durationMs / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function formatFailureDetail(result) {
  if (result.passed) {
    return "";
  }
  if (result.error) {
    return ` ${colour.yellow}${result.error.message}${colour.reset}`;
  }
  if (result.signal) {
    return ` ${colour.yellow}signal ${result.signal}${colour.reset}`;
  }
  return ` ${colour.yellow}exit ${result.status}${colour.reset}`;
}

function parseSelectedTasks(rawValue) {
  if (!rawValue) {
    return [];
  }

  return rawValue
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}
