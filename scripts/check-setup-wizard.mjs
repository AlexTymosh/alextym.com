#!/usr/bin/env node

import assert from "node:assert/strict";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import {
  applyAssignmentsToRaw,
  formatPath,
  getValueAtPath,
  listEditableFields,
  listEditableSections,
  loadProjectConfig,
  parsePath,
} from "./lib/project-config-wizard.mjs";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const tempDir = resolve(rootDir, ".tmp", "setup-wizard-check");
const tempConfigPath = resolve(tempDir, "project.config.json");
const rawCyrillicPattern = /[\u0400-\u04ff]/u;
const guiToken = "setup-wizard-check-token";

await runChecks();

async function runChecks() {
  rmSync(tempDir, { force: true, recursive: true });
  mkdirSync(tempDir, { recursive: true });

  try {
    const projectConfig = loadProjectConfig();
    const sections = listEditableSections(projectConfig.config);
    const sectionIds = sections.map((section) => section.id);

    assert(sectionIds.includes("siteIdentity"));
    assert(!sectionIds.includes("contactPage"));
    assert(!sectionIds.includes("chatHandoff"));
    assert(!sectionIds.includes("chatShell"));
    assert(sectionIds.includes("chatSettings"));
    assert(!sectionIds.includes("chatQuickPrompts"));
    assert(!sectionIds.includes("chatLanguageRestrictions"));
    assert(sectionIds.includes("disclaimerPage"));
    assert(sectionIds.includes("resumePdf"));
    assert(!sectionIds.includes("assistantCopy"));

    const chatFields = listEditableFields(projectConfig.config, "chatSettings");
    const chatFieldPaths = chatFields.map((field) => field.path);
    assert(chatFieldPaths.includes("chat.quickPrompts[0].label"));
    assert(chatFieldPaths.includes("chat.quickPrompts[0].responses"));
    assert(chatFieldPaths.includes("chat.languageRestrictions.russian.enabled"));
    assert(chatFieldPaths.includes("chat.languageRestrictions.ukrainian.enabled"));
    assert(chatFieldPaths.includes("chat.languageRestrictions.otherNonEnglish.enabled"));
    assert(!chatFieldPaths.includes("chat.languageRestrictions.russian.fallbackMessage"));
    assert(!chatFieldPaths.includes("chat.languageSupport.russian.enabled"));
    assert(!chatFieldPaths.includes("chat.shell.defaultInputPlaceholder"));
    assert(!chatFieldPaths.includes("chat.handoff.consentCopy"));
    assert(!chatFieldPaths.includes("chat.notices.assistantErrorMessage"));

    const resumeFields = listEditableFields(projectConfig.config, "resumePdf");
    const resumeFieldPaths = resumeFields.map((field) => field.path);
    assert(resumeFieldPaths.includes("resume.downloadFileNameBase"));
    assert(resumeFieldPaths.includes("resume.pdf.headerLinkVisibility.website"));
    assert(resumeFieldPaths.includes("resume.pdf.headerLinkVisibility.github"));
    assert(!resumeFieldPaths.includes("resume.introParagraphs"));
    assert(!resumeFieldPaths.includes("resume.pdf.headerLinks[0].text"));
    assert(!resumeFieldPaths.includes("resume.pdf.roleTitle"));
    assert(!resumeFieldPaths.includes("resume.pdf.profileText"));

    const siteFields = listEditableFields(projectConfig.config, "siteIdentity");
    const siteFieldPaths = siteFields.map((field) => field.path);
    assert(siteFieldPaths.includes("owner.shortName"));
    assert(siteFieldPaths.includes("owner.possessiveName"));
    assert(siteFieldPaths.includes("owner.localizedNames.russian"));
    assert(siteFieldPaths.includes("owner.localizedNames.ukrainian"));
    assert(siteFieldPaths.includes("seo.openGraph.imagePath"));
    assert(!siteFieldPaths.includes("site.language"));
    assert(!siteFieldPaths.includes("site.footer.message"));
    assert(!siteFieldPaths.includes("site.navigation[0].label"));
    assert(!siteFieldPaths.includes("links.website"));
    assert(!siteFieldPaths.includes("seo.titleTemplate"));
    assert(!siteFieldPaths.includes("seo.openGraph.imageWidth"));
    assert(!siteFieldPaths.includes("seo.jsonLd.personType"));

    const disclaimerFields = listEditableFields(projectConfig.config, "disclaimerPage");
    const disclaimerFieldPaths = disclaimerFields.map((field) => field.path);
    assert(disclaimerFieldPaths.includes("disclaimer.title"));
    assert(disclaimerFieldPaths.includes("disclaimer.bodyMarkdown"));
    assert(!disclaimerFieldPaths.includes("disclaimer.eyebrow"));

    assert.equal(
      formatPath(parsePath("chat.quickPrompts[0].responses")),
      "chat.quickPrompts[0].responses",
    );

    const currentPrompt = getValueAtPath(
      projectConfig.config,
      "chat.quickPrompts[0].label",
    );
    assert.equal(currentPrompt, "Give me your 1-minute intro.");

    const patchedOwner = applyAssignmentsToRaw(projectConfig.raw, projectConfig.config, [
      { path: "owner.shortName", rawValue: "Jordan" },
    ]);
    assert.equal(patchedOwner.changes.length, 1);
    assert.equal(JSON.parse(patchedOwner.patchedRaw).owner.shortName, "Jordan");
    assert.equal(
      JSON.parse(patchedOwner.patchedRaw).owner.displayName,
      projectConfig.config.owner.displayName,
    );
    assertNoRawCyrillic(patchedOwner.patchedRaw);

    const patchedArray = applyAssignmentsToRaw(projectConfig.raw, projectConfig.config, [
      { path: "owner.publicAliases", rawValue: "[\"jordan\",\"portfolio\"]" },
    ]);
    assert.deepEqual(JSON.parse(patchedArray.patchedRaw).owner.publicAliases, [
      "jordan",
      "portfolio",
    ]);

    const unchanged = applyAssignmentsToRaw(projectConfig.raw, projectConfig.config, [
      { path: "owner.shortName", rawValue: projectConfig.config.owner.shortName },
    ]);
    assert.equal(unchanged.changes.length, 0);
    assert.equal(unchanged.patchedRaw, projectConfig.raw);

    writeFileSync(tempConfigPath, projectConfig.raw, "utf8");
    const dryRun = spawnSync(
      process.execPath,
      [
        "scripts/setup-project-config.mjs",
        "--config",
        tempConfigPath,
        "--set",
        "owner.shortName=DryRunName",
        "--dry-run",
      ],
      {
        cwd: rootDir,
        encoding: "utf8",
      },
    );
    assert.equal(dryRun.status, 0, dryRun.stderr || dryRun.stdout);
    assert.equal(readFileSync(tempConfigPath, "utf8"), projectConfig.raw);

    const writeRun = spawnSync(
      process.execPath,
      [
        "scripts/setup-project-config.mjs",
        "--config",
        tempConfigPath,
        "--set",
        "owner.shortName=Pat",
      ],
      {
        cwd: rootDir,
        encoding: "utf8",
      },
    );
    assert.equal(writeRun.status, 0, writeRun.stderr || writeRun.stdout);

    const writtenRaw = readFileSync(tempConfigPath, "utf8");
    assert.equal(JSON.parse(writtenRaw).owner.shortName, "Pat");
    assertNoRawCyrillic(writtenRaw);

    writeFileSync(tempConfigPath, projectConfig.raw, "utf8");
    await assertGuiWizard(projectConfig.raw);

    console.log("Setup wizard check passed.");
  } finally {
    rmSync(tempDir, { force: true, recursive: true });
  }
}

async function assertGuiWizard(originalRaw) {
  const server = spawn(
    process.execPath,
    [
      "scripts/setup-project-config-gui.mjs",
      "--config",
      tempConfigPath,
      "--port",
      "0",
      "--no-open",
      "--token",
      guiToken,
    ],
    {
      cwd: rootDir,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  let serverUrl;
  let output = "";
  let shutdownRequested = false;

  try {
    serverUrl = await waitForServerUrl(server, (chunk) => {
      output += chunk;
    });

    const pageHtml = await requestText(`${serverUrl.origin}/`);
    assert(pageHtml.includes("mock-home-grid"));
    assert(pageHtml.includes("mock-project-items"));
    assert(!pageHtml.includes("Public profile URL available to home, contact, resume, or structured metadata."));
    assert(!pageHtml.includes("Example: URL:"));

    const state = await requestJson(`${serverUrl.origin}/api/state`);
    assert.equal(state.ok, true);
    assert(state.sections.some((section) => section.id === "chatSettings"));
    assert(!state.sections.some((section) => section.id === "chatQuickPrompts"));
    assert(!state.sections.some((section) => section.id === "chatLanguageRestrictions"));
    assert(state.sections.some((section) => section.id === "disclaimerPage"));
    assert(!state.sections.some((section) => section.id === "contactPage"));
    assert(!state.sections.some((section) => section.id === "chatHandoff"));
    assert(!state.sections.some((section) => section.id === "chatShell"));
    assert(
      state.fields.some(
        (field) =>
          field.path === "chat.languageRestrictions.russian.enabled" &&
          field.type === "boolean" &&
          field.readonlyPreview,
      ),
    );
    assert(
      !state.fields.some((field) => field.path.includes("fallbackMessage")),
    );
    assert(!state.fields.some((field) => field.path === "home.featuredProject.previewItems[0].slot"));
    assert(
      state.fields.some(
        (field) =>
          field.path === "resume.pdf.headerLinkVisibility.github" &&
          field.type === "boolean",
      ),
    );
    assert(
      state.fields.some(
        (field) =>
          field.path === "owner.shortName" &&
          field.pairGroup?.value === "owner-names",
      ),
    );
    assert(!state.fields.some((field) => field.path.startsWith("home.assistantCard.")));
    assert(
      state.fields.some(
        (field) =>
          field.path === "disclaimer.bodyMarkdown" &&
          field.description,
      ),
    );
    assert(!state.fields.some((field) => field.path === "contact.heading.title"));
    assert(!state.fields.some((field) => field.path === "resume.pdf.roleTitle"));
    assert(!state.fields.some((field) => field.path === "resume.pdf.profileText"));
    assert(!state.fields.some((field) => field.path === "resume.introParagraphs"));
    assert(!state.fields.some((field) => field.path === "resume.pdf.headerLinks[0].href"));
    assert(!state.fields.some((field) => field.path === "site.language"));
    assert(!state.fields.some((field) => field.path === "chat.handoff.consentCopy"));
    assert(!state.fields.some((field) => field.path === "chat.notices.assistantErrorMessage"));
    assert(!state.fields.some((field) => field.path === "assistant.publicScopeLabel"));
    assert(!state.fields.some((field) => field.path === "assistant.fixedAnswers.greeting"));
    assert(!state.fields.some((field) => field.path === "assistant.displayName"));
    assert(!state.fields.some((field) => field.path === "assistant.ownerReference"));
    assert(!state.fields.some((field) => field.path === "chat.shell.defaultInputPlaceholder"));
    assert(!state.fields.some((field) => field.path === "disclaimer.eyebrow"));
    assert(
      state.fields.some(
        (field) =>
          field.path === "links.github" &&
          field.description !==
            "Public profile URL available to home, contact, resume, or structured metadata.",
      ),
    );
    assert(
      state.fields.some(
        (field) =>
          field.path === "home.connectCard.linkVisibility.github" &&
          field.example === "",
      ),
    );
    assert(
      state.fields.some(
        (field) =>
          field.path === "home.featuredProject.previewItems[0].title" &&
          field.pairGroup?.value === "home-featured-preview-item-0",
      ),
    );

    const invalidPreview = await postJson(`${serverUrl.origin}/api/preview`, {
      assignments: [{ path: "owner.shortName", rawValue: "" }],
    });
    assert.equal(invalidPreview.ok, true);
    assert.equal(invalidPreview.validation.passed, false);
    assert(
      invalidPreview.validation.errors.some((error) =>
        error.includes("owner.shortName"),
      ),
    );
    assert.equal(readFileSync(tempConfigPath, "utf8"), originalRaw);

    const validPreview = await postJson(`${serverUrl.origin}/api/preview`, {
      assignments: [{ path: "owner.shortName", rawValue: "GuiName" }],
    });
    assert.equal(validPreview.ok, true);
    assert.equal(validPreview.validation.passed, true);
    assert.equal(validPreview.changes.length, 1);
    assert.equal(validPreview.changes[0].path, "owner.shortName");
    assert.equal(readFileSync(tempConfigPath, "utf8"), originalRaw);

    const rejectedSave = await postJson(`${serverUrl.origin}/api/save`, {
      assignments: [{ path: "owner.shortName", rawValue: "GuiName" }],
    });
    assert.equal(rejectedSave.ok, false);
    assert.equal(rejectedSave.requiresValidation, true);
    assert.equal(readFileSync(tempConfigPath, "utf8"), originalRaw);

    const saveResult = await postJson(`${serverUrl.origin}/api/save`, {
      assignments: [{ path: "owner.shortName", rawValue: "GuiName" }],
      validationKey: validPreview.validationKey,
    });
    assert.equal(saveResult.ok, true);
    assert.equal(saveResult.saved, true);

    const savedRaw = readFileSync(tempConfigPath, "utf8");
    assert.equal(JSON.parse(savedRaw).owner.shortName, "GuiName");
    assertNoRawCyrillic(savedRaw);

    const closeServer = await postJson(`${serverUrl.origin}/api/shutdown`, {});
    assert.equal(closeServer.ok, true);

    shutdownRequested = true;
  } finally {
    if (!shutdownRequested && !server.killed) {
      server.kill();
    }

    const exitCode = await waitForExit(server, shutdownRequested ? 10_000 : 2_000);
    assert(
      exitCode === 0 || exitCode === null,
      `GUI wizard exited with ${exitCode}. Output: ${output}`,
    );
  }
}

function waitForServerUrl(server, onChunk) {
  return new Promise((resolveUrl, rejectUrl) => {
    const timeout = setTimeout(() => {
      rejectUrl(new Error("Timed out waiting for GUI wizard server URL."));
    }, 10_000);

    function readChunk(chunk) {
      const text = chunk.toString();
      onChunk(text);
      const match = text.match(/http:\/\/127\.0\.0\.1:\d+\/\?token=[a-zA-Z0-9_-]+/);
      if (!match) {
        return;
      }

      clearTimeout(timeout);
      server.stdout.off("data", readChunk);
      resolveUrl(new URL(match[0]));
    }

    server.stdout.on("data", readChunk);
    server.stderr.on("data", (chunk) => onChunk(chunk.toString()));
    server.once("error", (error) => {
      clearTimeout(timeout);
      rejectUrl(error);
    });
    server.once("exit", (code) => {
      clearTimeout(timeout);
      rejectUrl(new Error(`GUI wizard exited before listening: ${code}`));
    });
  });
}

async function requestJson(url) {
  const response = await fetch(url, {
    headers: { "X-Wizard-Token": guiToken },
  });
  return response.json();
}

async function requestText(url) {
  const response = await fetch(url, {
    headers: { "X-Wizard-Token": guiToken },
  });
  return response.text();
}

async function postJson(url, body) {
  const response = await fetch(url, {
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      "X-Wizard-Token": guiToken,
    },
    method: "POST",
  });
  return response.json();
}

function waitForExit(server, timeoutMs) {
  return new Promise((resolveExit) => {
    if (server.exitCode !== null) {
      resolveExit(server.exitCode);
      return;
    }
    const timeout = setTimeout(() => {
      if (!server.killed) {
        server.kill();
      }
      resolveExit(server.exitCode);
    }, timeoutMs);
    server.once("exit", (code) => resolveExit(code));
    server.once("exit", () => clearTimeout(timeout));
  });
}

function assertNoRawCyrillic(rawValue) {
  assert.equal(rawCyrillicPattern.test(rawValue), false);
}
