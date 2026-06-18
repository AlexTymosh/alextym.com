#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cliOptions = parseCliOptions(process.argv.slice(2));
const configPath = cliOptions.configPath ?? "config/project.config.json";
const schemaPath = cliOptions.schemaPath ?? "config/project.config.schema.json";
const scriptPath = "scripts/check-project-config.mjs";
const rawCyrillicPattern = /[\u0400-\u04ff]/u;
const ukrainianSpecificPattern = /[\u0404\u0406\u0407\u0490\u0454\u0456\u0457\u0491]/u;
const allowedEmptyStringPaths = new Set(["home.profileCard.imageAlt"]);

const errors = [];

function fail(message) {
  errors.push(message);
}

function resolveProjectPath(pathValue) {
  return isAbsolute(pathValue) ? pathValue : resolve(rootDir, pathValue);
}

function displayPath(pathValue) {
  return isAbsolute(pathValue) ? pathValue : pathValue;
}

function readRaw(pathValue) {
  return readFileSync(resolveProjectPath(pathValue), "utf8");
}

function parseJson(pathValue) {
  const raw = readRaw(pathValue);

  try {
    return {
      raw,
      value: JSON.parse(raw),
    };
  } catch (error) {
    fail(`${displayPath(pathValue)} is not valid JSON: ${error.message}`);
    return {
      raw,
      value: {},
    };
  }
}

function assertNoRawCyrillic(relativePath, raw) {
  if (rawCyrillicPattern.test(raw)) {
    fail(`${relativePath} contains raw Cyrillic characters. Use escaped values or .ru documentation files.`);
  }
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function getPath(source, path) {
  return parseConfigPath(path).reduce((current, segment) => {
    if (!isPlainObject(current) && !Array.isArray(current)) {
      return undefined;
    }

    if (Array.isArray(current) && typeof segment !== "number") {
      return undefined;
    }

    return current[segment];
  }, source);
}

function parseConfigPath(path) {
  const segments = [];
  let token = "";
  let index = 0;

  while (index < path.length) {
    const character = path[index];

    if (character === ".") {
      if (token.length > 0) {
        segments.push(token);
        token = "";
      }
      index += 1;
      continue;
    }

    if (character === "[") {
      if (token.length > 0) {
        segments.push(token);
        token = "";
      }

      const endIndex = path.indexOf("]", index + 1);
      if (endIndex === -1) {
        return [path];
      }

      const rawIndex = path.slice(index + 1, endIndex);
      if (!/^\d+$/.test(rawIndex)) {
        return [path];
      }

      segments.push(Number(rawIndex));
      index = endIndex + 1;
      continue;
    }

    token += character;
    index += 1;
  }

  if (token.length > 0) {
    segments.push(token);
  }

  return segments;
}

function assertObject(source, path) {
  if (!isPlainObject(getPath(source, path))) {
    fail(`${path} must be an object.`);
  }
}

function assertNonEmptyString(source, path) {
  const value = getPath(source, path);
  if (typeof value !== "string" || value.trim().length === 0) {
    fail(`${path} must be a non-empty string.`);
  }
}

function assertNonEmptyArray(source, path) {
  const value = getPath(source, path);
  if (!Array.isArray(value) || value.length === 0) {
    fail(`${path} must be a non-empty array.`);
  }
}

function assertBoolean(source, path) {
  if (typeof getPath(source, path) !== "boolean") {
    fail(`${path} must be a boolean.`);
  }
}

function assertPathExists(source, path) {
  if (getPath(source, path) === undefined) {
    fail(`${path} must exist.`);
  }
}

function assertPathMissing(source, path) {
  if (getPath(source, path) !== undefined) {
    fail(`${path} must not be present.`);
  }
}

function assertUrl(source, path) {
  const value = getPath(source, path);
  if (typeof value !== "string") {
    fail(`${path} must be a URL string.`);
    return;
  }

  try {
    new URL(value);
  } catch {
    fail(`${path} must be a valid absolute URL.`);
  }
}

function assertUrlValue(path, value) {
  if (typeof value !== "string") {
    fail(`${path} must be a URL string.`);
    return;
  }

  try {
    new URL(value);
  } catch {
    fail(`${path} must be a valid absolute URL.`);
  }
}

function assertNoUnexpectedEmptyStrings(value, path = "") {
  if (typeof value === "string") {
    if (value.trim().length === 0 && !allowedEmptyStringPaths.has(path)) {
      fail(`${path} must not be empty.`);
    }
    return;
  }

  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      assertNoUnexpectedEmptyStrings(item, `${path}[${index}]`);
    });
    return;
  }

  if (!isPlainObject(value)) {
    return;
  }

  for (const [key, childValue] of Object.entries(value)) {
    assertNoUnexpectedEmptyStrings(childValue, path ? `${path}.${key}` : key);
  }
}

function assertRequiredTopLevel(config) {
  const requiredSections = [
    "$schema",
    "schemaVersion",
    "project",
    "content",
    "owner",
    "site",
    "links",
    "seo",
    "home",
    "contact",
    "chat",
    "disclaimer",
    "resume",
    "wizard",
  ];

  for (const section of requiredSections) {
    if (!(section in config)) {
      fail(`Missing top-level section: ${section}`);
    }
  }
}

function assertLinkConfig(config) {
  const links = getPath(config, "links");
  if (!isPlainObject(links)) {
    fail("links must be an object.");
    return;
  }

  for (const [key, value] of Object.entries(links)) {
    assertUrlValue(`links.${key}`, value);
  }

  const connectLinkVisibility = getPath(config, "home.connectCard.linkVisibility");
  if (!isPlainObject(connectLinkVisibility)) {
    fail("home.connectCard.linkVisibility must be an object.");
  } else {
    for (const [linkKey, isVisible] of Object.entries(connectLinkVisibility)) {
      if (typeof isVisible !== "boolean") {
        fail(`home.connectCard.linkVisibility.${linkKey} must be a boolean.`);
      }
      if (!(linkKey in links)) {
        fail(`home.connectCard.linkVisibility references missing links.${linkKey}.`);
      }
    }
  }

  const referencedLinkPaths = ["contact.socialLinks"];
  for (const linkPath of referencedLinkPaths) {
    const referencedLinks = getPath(config, linkPath);
    if (!Array.isArray(referencedLinks)) {
      fail(`${linkPath} must be an array.`);
      continue;
    }

    for (const linkKey of referencedLinks) {
      if (typeof linkKey !== "string" || !(linkKey in links)) {
        fail(`${linkPath} references missing links.${linkKey}.`);
      }
    }
  }
}

function assertResumeSourceExists(config) {
  const resumePath = getPath(config, "content.publicResumePath");
  if (typeof resumePath !== "string" || resumePath.trim().length === 0) {
    fail("content.publicResumePath must be a non-empty string.");
    return;
  }

  if (!existsSync(resolve(rootDir, resumePath))) {
    fail(`content.publicResumePath does not exist: ${resumePath}`);
  }
}

function parseCliOptions(args) {
  const options = {
    configPath: undefined,
    schemaPath: undefined,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];

    if (arg === "--config") {
      options.configPath = readOptionValue(args, index, arg);
      index += 1;
      continue;
    }

    if (arg === "--schema") {
      options.schemaPath = readOptionValue(args, index, arg);
      index += 1;
      continue;
    }

    throw new Error(`Unknown option: ${arg}`);
  }

  return options;
}

function readOptionValue(args, index, optionName) {
  const value = args[index + 1];

  if (!value || value.startsWith("--")) {
    throw new Error(`${optionName} requires a value.`);
  }

  return value;
}

function assertChatConfig(config) {
  assertNonEmptyArray(config, "chat.quickPrompts");
  assertObject(config, "chat.languageRestrictions");

  const quickPrompts = getPath(config, "chat.quickPrompts");
  if (Array.isArray(quickPrompts)) {
    const introPrompt = quickPrompts.find((prompt) =>
      isPlainObject(prompt) && String(prompt.label ?? "").includes("1-minute intro"),
    );
    if (!introPrompt) {
      fail("chat.quickPrompts must include the current 1-minute intro prompt.");
    }

    quickPrompts.forEach((prompt, index) => {
      if (!isPlainObject(prompt)) {
        fail(`chat.quickPrompts[${index}] must be an object.`);
        return;
      }
      if (typeof prompt.label !== "string" || prompt.label.trim().length === 0) {
        fail(`chat.quickPrompts[${index}].label must be a non-empty string.`);
      }
      if (!Array.isArray(prompt.responses) || prompt.responses.length === 0) {
        fail(`chat.quickPrompts[${index}].responses must be a non-empty array.`);
      }
    });
  }

  for (const languagePath of [
    "chat.languageRestrictions.russian",
    "chat.languageRestrictions.ukrainian",
    "chat.languageRestrictions.otherNonEnglish",
  ]) {
    assertBoolean(config, `${languagePath}.enabled`);
  }
}

function assertDisclaimerConfig(config) {
  assertNonEmptyString(config, "disclaimer.title");
  assertNonEmptyString(config, "disclaimer.bodyMarkdown");
}

function assertResumeConfig(config) {
  assertNonEmptyString(config, "resume.pageHeading");
  assertNonEmptyString(config, "resume.downloadFileNameBase");
  if (/\.pdf$/i.test(String(getPath(config, "resume.downloadFileNameBase")))) {
    fail("resume.downloadFileNameBase must not include the .pdf extension.");
  }

  assertObject(config, "resume.pdf.headerLinkVisibility");
  for (const path of [
    "resume.pdf.headerLinkVisibility.website",
    "resume.pdf.headerLinkVisibility.linkedin",
    "resume.pdf.headerLinkVisibility.github",
    "resume.pdf.headerLinkVisibility.facebook",
    "resume.pdf.headerLinkVisibility.rightToWorkUk",
  ]) {
    assertBoolean(config, path);
  }

  assertPathMissing(config, "resume.downloadFileName");
  assertPathMissing(config, "resume.introParagraphs");
  assertPathMissing(config, "resume.pdf.headerLinks");
  assertPathMissing(config, "resume.pdf.profileText");
}

function assertWizardConfig(config) {
  if (getPath(config, "wizard.behaviour.loadExistingConfig") !== true) {
    fail("wizard.behaviour.loadExistingConfig must be true.");
  }

  if (getPath(config, "wizard.behaviour.patchChangedFieldsOnly") !== true) {
    fail("wizard.behaviour.patchChangedFieldsOnly must be true.");
  }

  const sections = getPath(config, "wizard.editableSections");
  if (!Array.isArray(sections) || sections.length === 0) {
    fail("wizard.editableSections must be a non-empty array.");
    return;
  }

  const editablePaths = new Set(
    sections.flatMap((section) => {
      if (!isPlainObject(section) || !Array.isArray(section.paths)) {
        return [];
      }
      return section.paths;
    }),
  );

  const requiredEditablePaths = [
    "owner.displayName",
    "owner.shortName",
    "owner.possessiveName",
    "owner.localizedNames.russian",
    "owner.localizedNames.ukrainian",
    "site.name",
    "site.canonicalUrl",
    "seo.defaultTitle",
    "home.profileCard.summary",
    "home.connectCard.linkVisibility.github",
    "home.connectCard.linkVisibility.linkedin",
    "home.connectCard.linkVisibility.facebook",
    "chat.quickPrompts",
    "chat.languageRestrictions",
    "disclaimer",
    "resume.pageHeading",
    "resume.downloadFileNameBase",
    "resume.pdf.displayName",
    "resume.pdf.headerLinkVisibility.website",
    "resume.pdf.headerLinkVisibility.linkedin",
    "resume.pdf.headerLinkVisibility.github",
    "resume.pdf.headerLinkVisibility.facebook",
    "resume.pdf.headerLinkVisibility.rightToWorkUk",
  ];

  for (const requiredPath of requiredEditablePaths) {
    if (!editablePaths.has(requiredPath)) {
      fail(`wizard.editableSections must expose ${requiredPath}.`);
    }
  }

  const forbiddenEditablePaths = [
    "site.language",
    "site.footer",
    "site.navigation",
    "links.website",
    "seo.titleTemplate",
    "seo.openGraph.imageWidth",
    "seo.openGraph.imageHeight",
    "seo.jsonLd.personType",
    "chat.warmupMessages",
    "chat.thinkingMessages",
    "chat.shell",
    "chat.languageSupport",
    "chat.languageFallbacks",
    "chat.handoff",
    "chat.notices",
    "resume.downloadFileName",
    "resume.introParagraphs",
    "resume.pdf.headerLinks",
    "resume.pdf.profileText",
    "home",
    "home.profileCard.imageAlt",
    "home.assistantCard",
    "home.connectCard.eyebrow",
    "home.featuredProject.previewItems[0].slot",
    "home.featuredProject.previewItems[1].slot",
    "home.featuredProject.previewItems[2].slot",
    "assistant",
    "assistant.publicScopeLabel",
    "assistant.fixedAnswers",
  ];
  const exactOnlyForbiddenEditablePaths = new Set(["home"]);

  for (const forbiddenPath of forbiddenEditablePaths) {
    const exposedPath = Array.from(editablePaths).find(
      (editablePath) =>
        editablePath === forbiddenPath ||
        (!exactOnlyForbiddenEditablePaths.has(forbiddenPath) &&
          editablePath.startsWith(`${forbiddenPath}.`)),
    );
    if (exposedPath) {
      fail(`wizard.editableSections must not expose ${exposedPath}.`);
    }
  }

  for (const editablePath of editablePaths) {
    assertPathExists(config, editablePath);
  }
}

function assertSchemaContract(schema) {
  if (schema.$schema !== "https://json-schema.org/draft/2020-12/schema") {
    fail("Schema must use JSON Schema draft 2020-12.");
  }

  if (!Array.isArray(schema.required)) {
    fail("Schema must define required top-level sections.");
    return;
  }

  for (const requiredSection of [
    "chat",
    "disclaimer",
    "wizard",
    "content",
    "owner",
    "site",
    "seo",
  ]) {
    if (!schema.required.includes(requiredSection)) {
      fail(`Schema must require ${requiredSection}.`);
    }
  }
}

const configFile = parseJson(configPath);
const schemaFile = parseJson(schemaPath);

assertNoRawCyrillic(displayPath(configPath), configFile.raw);
assertNoRawCyrillic(displayPath(schemaPath), schemaFile.raw);
assertNoRawCyrillic(scriptPath, readRaw(scriptPath));

const config = configFile.value;
const schema = schemaFile.value;

assertRequiredTopLevel(config);
assertSchemaContract(schema);

if (config.$schema !== "./project.config.schema.json") {
  fail("config.$schema must point to ./project.config.schema.json.");
}

if (config.schemaVersion !== 1) {
  fail("config.schemaVersion must be 1.");
}

assertNonEmptyString(config, "project.templateName");
assertNonEmptyString(config, "project.packageBaseName");
assertNonEmptyString(config, "owner.displayName");
assertNonEmptyString(config, "owner.shortName");
assertNonEmptyString(config, "owner.possessiveName");
assertNonEmptyString(config, "owner.localizedNames.russian");
assertNonEmptyString(config, "owner.localizedNames.ukrainian");
if (!rawCyrillicPattern.test(String(getPath(config, "owner.localizedNames.russian")))) {
  fail("owner.localizedNames.russian must decode to Cyrillic text.");
}
if (!rawCyrillicPattern.test(String(getPath(config, "owner.localizedNames.ukrainian")))) {
  fail("owner.localizedNames.ukrainian must decode to Cyrillic text.");
}
if (!ukrainianSpecificPattern.test(String(getPath(config, "owner.localizedNames.ukrainian")))) {
  fail("owner.localizedNames.ukrainian should contain Ukrainian-specific letters.");
}
assertNonEmptyString(config, "owner.roleTitle");
assertNonEmptyString(config, "site.name");
assertUrl(config, "site.canonicalUrl");
assertPathMissing(config, "site.domain");
assertPathMissing(config, "links.website");
assertPathMissing(config, "site.language");
assertPathMissing(config, "site.footer");
assertPathMissing(config, "site.navigation");
assertPathMissing(config, "seo.titleTemplate");
assertPathMissing(config, "seo.openGraph.imageWidth");
assertPathMissing(config, "seo.openGraph.imageHeight");
assertPathMissing(config, "seo.jsonLd.personType");
assertPathMissing(config, "chat.shell");
assertPathMissing(config, "chat.languageFallbacks");
assertPathMissing(config, "chat.handoff");
assertPathMissing(config, "chat.notices");
assertPathMissing(config, "chat.languageSupport");
assertPathMissing(config, "chat.warmupMessages");
assertPathMissing(config, "chat.thinkingMessages");
assertPathMissing(config, "disclaimer.eyebrow");
assertPathMissing(config, "disclaimer.sections");
assertPathMissing(config, "assistant");
assertPathMissing(config, "assistant.publicScopeLabel");
assertPathMissing(config, "assistant.fixedAnswers");
assertPathMissing(config, "home.connectCard.links");
assertPathMissing(config, "resume.downloadFileName");
assertPathMissing(config, "resume.introParagraphs");
assertPathMissing(config, "resume.pdf.headerLinks");
assertLinkConfig(config);
assertNonEmptyString(config, "seo.defaultTitle");
assertNonEmptyString(config, "seo.description");
assertNonEmptyArray(config, "seo.keywords");
assertResumeSourceExists(config);
assertChatConfig(config);
assertDisclaimerConfig(config);
assertResumeConfig(config);
assertWizardConfig(config);
assertNoUnexpectedEmptyStrings(config);

if (errors.length > 0) {
  console.error("Project config check failed:");
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log("Project config check passed.");
