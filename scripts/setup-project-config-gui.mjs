#!/usr/bin/env node

import { createHash, randomBytes } from "node:crypto";
import { createServer } from "node:http";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawn } from "node:child_process";

import {
  applyAssignmentsToRaw,
  DEFAULT_CONFIG_PATH,
  getFollowUpActions,
  listEditableFields,
  listEditableSections,
  loadProjectConfig,
  REPO_ROOT,
  resolveProjectPath,
  runProjectConfigValidation,
  writeProjectConfig,
} from "./lib/project-config-wizard.mjs";

main().catch((error) => {
  console.error(`Setup wizard GUI failed: ${error.message}`);
  process.exit(1);
});

async function main() {
  const options = parseCliOptions(process.argv.slice(2));
  const host = options.host;
  assertLoopbackHost(host);
  const token = options.token ?? randomBytes(18).toString("hex");
  const configPath = resolveProjectPath(options.configPath ?? DEFAULT_CONFIG_PATH);
  const state = {
    lastValidationKey: null,
  };

  const server = createServer(async (request, response) => {
    try {
      await handleRequest({
        configPath,
        request,
        response,
        server,
        state,
        token,
      });
    } catch (error) {
      sendJson(response, error.status ?? 500, {
        error: error.message,
        ok: false,
      });
    }
  });

  await listen(server, options.port, host);

  const address = server.address();
  const port = typeof address === "object" && address ? address.port : options.port;
  const url = `http://${host}:${port}/?token=${encodeURIComponent(token)}`;

  console.log(`Setup wizard GUI listening on ${url}`);
  console.log("This server is local only. Use Finish setup or press Ctrl+C to stop it.");

  if (options.openBrowser) {
    openBrowser(url);
  }
}

async function handleRequest(context) {
  const { request, response, token } = context;
  const url = new URL(request.url ?? "/", "http://127.0.0.1");

  if (request.method === "GET" && url.pathname === "/") {
    sendHtml(response, renderPage(token));
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/health") {
    requireToken(request, token);
    sendJson(response, 200, {
      ok: true,
    });
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/state") {
    requireToken(request, token);
    sendJson(response, 200, getWizardState(context.configPath));
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/preview") {
    requireToken(request, token);
    const body = await readJsonBody(request);
    const preview = previewAssignments(context.configPath, body.assignments ?? []);

    context.state.lastValidationKey = preview.validation.passed
      ? preview.validationKey
      : null;

    sendJson(response, 200, preview);
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/save") {
    requireToken(request, token);
    const body = await readJsonBody(request);
    const saved = saveAssignments({
      assignments: body.assignments ?? [],
      configPath: context.configPath,
      expectedValidationKey: context.state.lastValidationKey,
      validationKey: body.validationKey,
    });

    if (saved.ok) {
      context.state.lastValidationKey = null;
    }
    sendJson(response, 200, saved);
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/shutdown") {
    requireToken(request, token);
    sendJson(response, 200, {
      ok: true,
    });
    context.server.close();
    return;
  }

  sendJson(response, 404, {
    error: "Not found.",
    ok: false,
  });
}

function getWizardState(configPath) {
  const projectConfig = loadProjectConfig(configPath);
  const sections = listEditableSections(projectConfig.config).map((section) => ({
    ...section,
    description: getSectionDescription(section.id),
    fieldCount: listEditableFields(projectConfig.config, section.id).length,
  }));
  const fields = listEditableFields(projectConfig.config).map((field) => ({
    description: getFieldDescription(field.path),
    example: getFieldExample(field, projectConfig.config),
    group: getFieldGroup(field.path),
    label: getFieldLabel(field.path),
    options: getFieldOptions(field.path),
    pairGroup: getPairGroup(field.path),
    path: field.path,
    readonlyPreview: getReadonlyPreview(field.path, projectConfig.config),
    sectionId: field.sectionId,
    sectionTitle: field.sectionTitle,
    type: getFieldType(field.value),
    value: field.value,
  }));

  return {
    configPath: projectConfig.path,
    fields,
    followUpActions: getFollowUpActions(projectConfig.config),
    ok: true,
    sections,
  };
}

function previewAssignments(configPath, rawAssignments) {
  const assignments = normaliseAssignments(rawAssignments);
  const projectConfig = loadProjectConfig(configPath);
  const result = applyAssignmentsToRaw(
    projectConfig.raw,
    projectConfig.config,
    assignments,
  );
  const validation = validatePatchedRaw(result.patchedRaw);
  const validationKey = hashAssignments(assignments);

  return {
    changes: result.changes.map((change) => ({
      newValue: change.newValue,
      oldValue: change.oldValue,
      path: change.path,
    })),
    followUpActions: getFollowUpActions(result.config),
    ok: true,
    validation,
    validationKey,
  };
}

function saveAssignments({
  assignments: rawAssignments,
  configPath,
  expectedValidationKey,
  validationKey,
}) {
  const assignments = normaliseAssignments(rawAssignments);
  const assignmentKey = hashAssignments(assignments);

  if (!validationKey || validationKey !== expectedValidationKey) {
    return {
      error: "Save requires a successful review and validation of the current changes.",
      ok: false,
      requiresValidation: true,
    };
  }

  if (validationKey !== assignmentKey) {
    return {
      error: "Changes were edited after validation. Review and validate them again before saving.",
      ok: false,
      requiresValidation: true,
    };
  }

  const projectConfig = loadProjectConfig(configPath);
  const result = applyAssignmentsToRaw(
    projectConfig.raw,
    projectConfig.config,
    assignments,
  );

  if (result.changes.length === 0) {
    return {
      changes: [],
      ok: true,
      saved: false,
      validation: {
        errors: [],
        output: "No changes.",
        passed: true,
      },
    };
  }

  writeProjectConfig(projectConfig.path, result.patchedRaw);
  const validation = runProjectConfigValidation(projectConfig.path);
  const validationResult = normaliseValidationResult(validation);

  if (!validationResult.passed) {
    writeProjectConfig(projectConfig.path, projectConfig.raw);
    return {
      changes: result.changes,
      error: "Validation failed after writing. The original config was restored.",
      ok: false,
      saved: false,
      validation: validationResult,
    };
  }

  return {
    changes: result.changes.map((change) => ({
      newValue: change.newValue,
      oldValue: change.oldValue,
      path: change.path,
    })),
    ok: true,
    saved: true,
    validation: validationResult,
  };
}

function validatePatchedRaw(patchedRaw) {
  const tempDir = resolve(REPO_ROOT, ".tmp", "setup-wizard-preview");
  const tempConfigPath = resolve(
    tempDir,
    `project.config.${process.pid}.${Date.now()}.json`,
  );

  mkdirSync(tempDir, { recursive: true });
  writeFileSync(tempConfigPath, patchedRaw, "utf8");

  try {
    return normaliseValidationResult(runProjectConfigValidation(tempConfigPath));
  } finally {
    rmSync(tempConfigPath, { force: true });
  }
}

function normaliseValidationResult(result) {
  const output = [result.stdout, result.stderr]
    .filter(Boolean)
    .join("")
    .trim();
  const errors = output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2));

  return {
    errors,
    output,
    passed: result.status === 0 && !result.error,
  };
}

function normaliseAssignments(rawAssignments) {
  if (!Array.isArray(rawAssignments)) {
    throw new Error("assignments must be an array.");
  }

  return rawAssignments
    .map((assignment) => {
      if (
        !assignment ||
        typeof assignment.path !== "string" ||
        typeof assignment.rawValue !== "string"
      ) {
        throw new Error("Each assignment must include string path and rawValue fields.");
      }

      return {
        path: assignment.path,
        rawValue: assignment.rawValue,
      };
    })
    .sort((left, right) => left.path.localeCompare(right.path));
}

function hashAssignments(assignments) {
  return createHash("sha256")
    .update(JSON.stringify(normaliseAssignments(assignments)))
    .digest("hex");
}

function getFieldType(value) {
  if (Array.isArray(value)) {
    return "array";
  }

  if (value === null) {
    return "null";
  }

  return typeof value;
}

function getFieldOptions(path) {
  return null;
}

function getPairGroup(path) {
  const ownerNameFields = {
    "owner.displayName": 0,
    "owner.localizedNames.russian": 3,
    "owner.localizedNames.ukrainian": 4,
    "owner.possessiveName": 2,
    "owner.shortName": 1,
  };

  if (Object.hasOwn(ownerNameFields, path)) {
    return {
      label: "Owner names",
      order: ownerNameFields[path],
      value: "owner-names",
    };
  }

  const websiteFields = {
    "site.canonicalUrl": 1,
    "site.name": 0,
  };
  if (Object.hasOwn(websiteFields, path)) {
    return {
      label: "Website",
      order: websiteFields[path],
      value: "website-identity",
    };
  }

  const publicLinkFields = {
    "links.facebook": 2,
    "links.github": 0,
    "links.linkedin": 1,
  };
  if (Object.hasOwn(publicLinkFields, path)) {
    return {
      label: "Public profile links",
      order: publicLinkFields[path],
      value: "public-profile-links",
    };
  }

  const connectVisibilityMatch = path.match(/^home\.connectCard\.linkVisibility\.([^.]+)$/);
  if (connectVisibilityMatch) {
    return {
      label: "Links to show in Connect",
      order: ["github", "linkedin", "facebook"].indexOf(connectVisibilityMatch[1]),
      value: "home-connect-link-visibility",
    };
  }

  const resumeLinkVisibilityMatch = path.match(
    /^resume\.pdf\.headerLinkVisibility\.([^.]+)$/,
  );
  if (resumeLinkVisibilityMatch) {
    return {
      label: "Links to include in the resume PDF",
      order: ["website", "linkedin", "github", "facebook", "rightToWorkUk"].indexOf(
        resumeLinkVisibilityMatch[1],
      ),
      value: "resume-pdf-link-visibility",
    };
  }

  const featuredPreviewItemMatch = path.match(
    /^home\.featuredProject\.previewItems\[(\d+)\]\.(title|detail|href)$/,
  );
  if (featuredPreviewItemMatch) {
    return {
      label: `Preview item ${Number(featuredPreviewItemMatch[1]) + 1}`,
      order: {
        detail: 2,
        href: 1,
        title: 0,
      }[featuredPreviewItemMatch[2]],
      value: `home-featured-preview-item-${featuredPreviewItemMatch[1]}`,
    };
  }

  return null;
}

function getFieldGroup(path) {
  const groupRules = [
    [/^owner\./, "owner", "Owner identity", "Names and public owner labels used across the site."],
    [/^site\./, "website", "Website", "Public website name and canonical URL."],
    [/^links\./, "public-links", "Public links", "Social and profile links shown on the site."],
    [/^seo\.openGraph\./, "seo-social-preview", "Social preview", "Preview image metadata for shared links."],
    [/^seo\.jsonLd\./, "seo-structured-data", "Structured data", "Public person metadata for search engines."],
    [/^seo\.pages\./, "seo-page-descriptions", "Page SEO descriptions", "Search-result descriptions for public pages."],
    [/^seo\./, "seo-general", "Main SEO", "Main browser and search metadata."],
    [/^home\.profileCard\./, "home-profile-card", "Profile card", "Top home page card with the owner photo and summary."],
    [/^home\.connectCard\.linkVisibility\./, "home-connect-card", "Connect links", "Choose which canonical public links appear in the Connect card."],
    [/^home\.featuredProject\./, "home-featured-project", "Featured project", "Main project block and repository preview items on the home page."],
    [/^home\.featuredAutomationDemo\./, "home-automation-demo", "Automation demo", "Home page video/demo block."],
    [/^home\.buildFocus\./, "home-build-focus", "Current focus", "Home page block describing the current engineering focus."],
    [/^home\.projectStack/, "home-project-stack", "Project stack", "Technology list shown on the home page."],
    [/^chat\.quickPrompts\[(\d+)\]\./, null, "Quick prompt", "One clickable prompt and its scripted response variants."],
    [/^chat\.languageRestrictions\.russian\./, "chat-language-russian", "Russian restriction", "Block Russian answers and show the system fallback preview."],
    [/^chat\.languageRestrictions\.ukrainian\./, "chat-language-ukrainian", "Ukrainian restriction", "Block Ukrainian answers and show the system fallback preview."],
    [/^chat\.languageRestrictions\.otherNonEnglish\./, "chat-language-other", "Other non-English restriction", "Block other non-English answers and show the system fallback preview."],
    [/^resume\.pdf\.headerLinkVisibility\./, "resume-pdf-links", "Resume PDF links", "Choose which canonical public links appear in the generated PDF."],
    [/^resume\.pdf\./, "resume-pdf", "Resume PDF", "Public header fields used in the generated PDF."],
    [/^resume\./, "resume-page", "Resume page", "Public resume page labels and download settings."],
    [/^disclaimer\./, "disclaimer-page", "Disclaimer", "Full public disclaimer page content."],
  ];

  for (const [pattern, fixedValue, label, description] of groupRules) {
    const match = path.match(pattern);
    if (!match) {
      continue;
    }

    const value = fixedValue ?? `${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${match[1]}`;
    const suffix = match[1] ? ` ${Number(match[1]) + 1}` : "";
    return {
      description,
      label: `${label}${suffix}`,
      value,
    };
  }

  return null;
}

function getFieldLabel(path) {
  const labels = {
    "content.publicResumePath": "Public resume source path",
    "disclaimer.bodyMarkdown": "Disclaimer full text",
    "disclaimer.title": "Disclaimer page title",
    "home.buildFocus.description": "Current focus description",
    "home.buildFocus.eyebrow": "Current focus eyebrow",
    "home.buildFocus.title": "Current focus title",
    "home.connectCard.linkVisibility.facebook": "Facebook",
    "home.connectCard.linkVisibility.github": "GitHub",
    "home.connectCard.linkVisibility.linkedin": "LinkedIn",
    "home.featuredAutomationDemo.cta": "Demo button text",
    "home.featuredAutomationDemo.description": "Demo description",
    "home.featuredAutomationDemo.eyebrow": "Demo eyebrow",
    "home.featuredAutomationDemo.title": "Demo title",
    "home.featuredAutomationDemo.youtubeTitle": "YouTube video title",
    "home.featuredAutomationDemo.youtubeVideoId": "YouTube video ID",
    "home.featuredProject.cta": "Featured project button text",
    "home.featuredProject.description": "Featured project description",
    "home.featuredProject.href": "Featured project link",
    "home.featuredProject.previewHeading": "Preview heading",
    "home.featuredProject.title": "Featured project title",
    "home.profileCard.imageSrc": "Profile image path",
    "home.profileCard.name": "Profile card name",
    "home.profileCard.summary": "Profile card summary",
    "home.projectStack": "Project stack list",
    "home.projectStackTitle": "Project stack title",
    "links.facebook": "Facebook URL",
    "links.github": "GitHub URL",
    "links.linkedin": "LinkedIn URL",
    "owner.displayName": "Full public name",
    "owner.localizedNames.russian": "Russian public name",
    "owner.localizedNames.ukrainian": "Ukrainian public name",
    "owner.possessiveName": "Possessive short name",
    "owner.publicAliases": "Search aliases",
    "owner.roleTitle": "Public role title",
    "owner.shortName": "Short public name",
    "resume.downloadFileNameBase": "Downloaded PDF base name",
    "resume.pageHeading": "Resume page heading",
    "resume.pdf.displayName": "PDF display name",
    "resume.pdf.headerLinkVisibility.facebook": "Facebook",
    "resume.pdf.headerLinkVisibility.github": "GitHub",
    "resume.pdf.headerLinkVisibility.linkedin": "LinkedIn",
    "resume.pdf.headerLinkVisibility.rightToWorkUk": "Right to work in the UK",
    "resume.pdf.headerLinkVisibility.website": "Website",
    "seo.defaultTitle": "Home page browser title",
    "seo.description": "Main SEO description",
    "seo.keywords": "SEO keywords",
    "seo.openGraph.imageAlt": "Social preview image alt text",
    "seo.openGraph.imagePath": "Social preview image path",
    "seo.shortDescription": "Short social preview description",
    "site.canonicalUrl": "Website URL",
    "site.name": "Site display name",
  };

  if (labels[path]) {
    return labels[path];
  }

  const quickPromptMatch = path.match(/^chat\.quickPrompts\[(\d+)\]\.(label|responses)$/);
  if (quickPromptMatch) {
    return quickPromptMatch[2] === "label"
      ? `Quick prompt ${Number(quickPromptMatch[1]) + 1} label`
      : `Quick prompt ${Number(quickPromptMatch[1]) + 1} responses`;
  }

  const previewItemMatch = path.match(
    /^home\.featuredProject\.previewItems\[(\d+)\]\.(title|detail|href)$/,
  );
  if (previewItemMatch) {
    return `Preview item ${Number(previewItemMatch[1]) + 1} ${humanisePathToken(previewItemMatch[2])}`;
  }

  const languageRestrictionMatch = path.match(
    /^chat\.languageRestrictions\.(russian|ukrainian|otherNonEnglish)\.enabled$/,
  );
  if (languageRestrictionMatch) {
    const languageLabel = humanisePathToken(languageRestrictionMatch[1]);
    return `Block ${languageLabel} replies`;
  }

  const seoPageMatch = path.match(/^seo\.pages\.([^.]+)\.description$/);
  if (seoPageMatch) {
    return `${humanisePathToken(seoPageMatch[1])} SEO description`;
  }

  return humanisePathToken(path.split(".").at(-1) ?? path);
}

function getFieldDescription(path) {
  if (path.startsWith("owner.")) {
    return "Used in headings, assistant copy, SEO metadata, and generated defaults.";
  }
  if (path === "site.name") {
    return "Shown as the site brand in the header, footer, and app metadata.";
  }
  if (path === "site.canonicalUrl") {
    return "Main public URL with https. The domain and website link are derived from it.";
  }
  if (path.startsWith("links.")) {
    return "Set this public profile URL once. Page sections only choose whether to show it.";
  }
  if (path.startsWith("seo.openGraph.")) {
    return "Used when the site is shared in social networks or messengers.";
  }
  if (path.startsWith("seo.pages.")) {
    return "Used as the meta description for this public page.";
  }
  if (path.startsWith("seo.")) {
    return "Used by search engines and browser metadata.";
  }
  if (path.startsWith("home.")) {
    return "Shown on the home page.";
  }
  if (path.startsWith("chat.quickPrompts")) {
    return "Shown as a clickable chat shortcut and its local scripted answer variants.";
  }
  if (path.startsWith("chat.languageRestrictions.russian")) {
    return "If checked, Russian messages are blocked and the visitor sees the system fallback phrase.";
  }
  if (path.startsWith("chat.languageRestrictions.ukrainian")) {
    return "If checked, Ukrainian messages are blocked and the visitor sees the system fallback phrase.";
  }
  if (path.startsWith("chat.languageRestrictions")) {
    return "If checked, matching non-English messages are replaced with a code-owned system fallback.";
  }
  if (path.startsWith("resume.")) {
    return "Shown on the resume page or in the generated PDF.";
  }
  if (path.startsWith("disclaimer.")) {
    return "Shown on the public disclaimer page. The body supports simple Markdown headings such as ## Purpose.";
  }
  return "Editable public project setting.";
}

function getSectionDescription(sectionId) {
  const descriptions = {
    chatSettings: "Clickable chat prompts, scripted answer variants, and language restriction switches.",
    disclaimerPage: "Public disclaimer page content.",
    homePage: "Text, links, cards, and project blocks on the home page.",
    resumePdf: "Resume page heading, PDF public header, and link visibility.",
    siteIdentity: "Owner identity, website URL, public links, and SEO descriptions.",
  };

  return descriptions[sectionId] ?? "Editable public project settings.";
}

function humanisePathToken(value) {
  return value
    .replace(/\[(\d+)\]/g, " $1")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/^./, (character) => character.toUpperCase());
}

function getFieldExample(field, config) {
  const { path, value } = field;

  if (path === "disclaimer.bodyMarkdown") {
    return "## Purpose\n\nFull disclaimer text here.";
  }

  if (/^chat\.quickPrompts\[\d+\]\.responses$/.test(path)) {
    return "Each response variant is edited separately. Use normal line breaks inside each response.";
  }

  const homeLinkVisibilityMatch = path.match(/^home\.connectCard\.linkVisibility\.([^.]+)$/);
  if (homeLinkVisibilityMatch) {
    return "";
  }

  const pdfHeaderVisibilityMatch = path.match(
    /^resume\.pdf\.headerLinkVisibility\.([^.]+)$/,
  );
  if (pdfHeaderVisibilityMatch) {
    const key = pdfHeaderVisibilityMatch[1];
    if (key === "website") {
      return `URL: ${config.site?.canonicalUrl ?? "Set the website URL in Site identity."}`;
    }
    if (key === "rightToWorkUk") {
      return "Displays text: Right to work in UK";
    }
    return `URL: ${config.links?.[key] ?? "Set this URL in Public links."}`;
  }

  if (/\.href$/.test(path) || path.includes("Url") || path.startsWith("links.")) {
    return "https://example.com/";
  }

  if (path === "resume.downloadFileNameBase") {
    return "Your_Name_CV";
  }

  if (/domain$/.test(path)) {
    return "example.com";
  }

  if (/canonical$/.test(path)) {
    return "/resume";
  }

  if (Array.isArray(value)) {
    return JSON.stringify(value, null, 2);
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }

  return "Example value";
}

function getReadonlyPreview(path, config) {
  const match = path.match(
    /^chat\.languageRestrictions\.(russian|ukrainian|otherNonEnglish)\.enabled$/,
  );
  if (!match) {
    return null;
  }

  const ownerReference = config.owner?.shortName ?? "the site owner";
  const russianName = config.owner?.localizedNames?.russian ?? ownerReference;
  const ukrainianName = config.owner?.localizedNames?.ukrainian ?? ownerReference;

  if (match[1] === "russian") {
    return (
      "\u0418\u0437\u0432\u0438\u043d\u0438\u0442\u0435, " +
      russianName +
      " \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0438\u043b " +
      "\u043c\u0435\u043d\u044f \u0432 \u043e\u0431\u0449\u0435\u043d\u0438\u0438 " +
      "\u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c " +
      "\u044f\u0437\u044b\u043a\u0435. \u042f \u043c\u043e\u0433\u0443 " +
      "\u043e\u0442\u0432\u0435\u0447\u0430\u0442\u044c " +
      "\u0442\u043e\u043b\u044c\u043a\u043e " +
      "\u043f\u043e-\u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438.\n" +
      "\u0414\u043b\u044f \u043e\u0431\u0449\u0435\u043d\u0438\u044f " +
      "\u043f\u043e-\u0440\u0443\u0441\u0441\u043a\u0438 \u044f " +
      "\u043c\u043e\u0433\u0443 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0438\u0442\u044c " +
      "\u043f\u0440\u044f\u043c\u043e\u0435 \u043e\u0431\u0449\u0435\u043d\u0438\u0435."
    );
  }

  if (match[1] === "ukrainian") {
    return (
      "\u0412\u0438\u0431\u0430\u0447\u0442\u0435, " +
      ukrainianName +
      " \u043e\u0431\u043c\u0435\u0436\u0438\u0432 \u043c\u0435\u043d\u0435 " +
      "\u0443 \u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u043d\u043d\u0456 " +
      "\u0443\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u043e\u044e " +
      "\u043c\u043e\u0432\u043e\u044e. \u042f \u043c\u043e\u0436\u0443 " +
      "\u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u0430\u0442\u0438 " +
      "\u043b\u0438\u0448\u0435 " +
      "\u0430\u043d\u0433\u043b\u0456\u0439\u0441\u044c\u043a\u043e\u044e.\n" +
      "\u042f\u043a\u0449\u043e \u0432\u0430\u043c \u0437\u0440\u0443\u0447\u043d\u0456\u0448\u0435 " +
      "\u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u0442\u0438\u0441\u044f " +
      "\u0440\u0456\u0434\u043d\u043e\u044e \u043c\u043e\u0432\u043e\u044e, " +
      "\u044f \u043c\u043e\u0436\u0443 " +
      "\u0437\u0430\u043f\u0440\u043e\u043f\u043e\u043d\u0443\u0432\u0430\u0442\u0438 " +
      "\u043f\u0440\u044f\u043c\u0435 \u0437\u0432\u0435\u0440\u043d\u0435\u043d\u043d\u044f."
    );
  }

  return (
    `Sorry, ${ownerReference} has limited me to English.\n` +
    "Please ask your question in English, or use the contact option below " +
    `to reach ${ownerReference} directly.`
  );
}

function requireToken(request, expectedToken) {
  const token = request.headers["x-wizard-token"];

  if (token !== expectedToken) {
    const error = new Error("Invalid wizard token.");
    error.status = 403;
    throw error;
  }
}

function readJsonBody(request) {
  return new Promise((resolveBody, rejectBody) => {
    let rawBody = "";

    request.on("data", (chunk) => {
      rawBody += chunk;
      if (rawBody.length > 2_000_000) {
        rejectBody(new Error("Request body is too large."));
        request.destroy();
      }
    });

    request.on("end", () => {
      if (!rawBody) {
        resolveBody({});
        return;
      }

      try {
        resolveBody(JSON.parse(rawBody));
      } catch (error) {
        rejectBody(new Error(`Invalid JSON body: ${error.message}`));
      }
    });

    request.on("error", rejectBody);
  });
}

function sendHtml(response, body) {
  response.writeHead(200, {
    "Cache-Control": "no-store",
    "Content-Type": "text/html; charset=utf-8",
  });
  response.end(body);
}

function sendJson(response, status, body) {
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
  });
  response.end(JSON.stringify(body));
}

function listen(server, port, host) {
  return new Promise((resolveListen, rejectListen) => {
    server.once("error", rejectListen);
    server.listen(port, host, () => {
      server.off("error", rejectListen);
      resolveListen();
    });
  });
}

function openBrowser(url) {
  const platform = process.platform;

  if (platform === "win32") {
    spawn("cmd", ["/c", "start", "", url], {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    }).unref();
    return;
  }

  if (platform === "darwin") {
    spawn("open", [url], {
      detached: true,
      stdio: "ignore",
    }).unref();
    return;
  }

  spawn("xdg-open", [url], {
    detached: true,
    stdio: "ignore",
  }).unref();
}

function parseCliOptions(args) {
  const options = {
    configPath: undefined,
    host: "127.0.0.1",
    openBrowser: true,
    port: 0,
    token: undefined,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];

    if (arg === "--config") {
      options.configPath = readOptionValue(args, index, arg);
      index += 1;
      continue;
    }

    if (arg === "--host") {
      options.host = readOptionValue(args, index, arg);
      index += 1;
      continue;
    }

    if (arg === "--port") {
      options.port = Number(readOptionValue(args, index, arg));
      if (!Number.isInteger(options.port) || options.port < 0) {
        throw new Error("--port must be a non-negative integer.");
      }
      index += 1;
      continue;
    }

    if (arg === "--token") {
      options.token = readOptionValue(args, index, arg);
      index += 1;
      continue;
    }

    if (arg === "--no-open") {
      options.openBrowser = false;
      continue;
    }

    if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    }

    throw new Error(`Unknown option: ${arg}`);
  }

  return options;
}

function assertLoopbackHost(host) {
  const allowedHosts = new Set(["127.0.0.1", "localhost"]);

  if (!allowedHosts.has(host)) {
    throw new Error("The setup wizard GUI may only bind to a loopback host.");
  }
}

function readOptionValue(args, index, optionName) {
  const value = args[index + 1];

  if (!value || value.startsWith("--")) {
    throw new Error(`${optionName} requires a value.`);
  }

  return value;
}

function printHelp() {
  console.log(`Usage:
  node scripts/setup-project-config-gui.mjs [options]

Options:
  --config <path>   Use a project config file. Defaults to config/project.config.json.
  --host <host>     Bind host. Defaults to 127.0.0.1.
  --port <port>     Bind port. Defaults to 0, which selects a free port.
  --no-open         Print the URL without opening a browser.
  --token <token>   Use a fixed local API token. Intended for tests.
  --help            Show this help.
`);
}

function renderPage(token) {
  const encodedToken = JSON.stringify(token);

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Project Setup Wizard</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-strong: #f0f4f8;
      --border: #d7dee8;
      --border-strong: #a9b6c8;
      --text: #182230;
      --muted: #667085;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --danger: #b42318;
      --warning: #b54708;
      --success: #027a48;
      --shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      background: var(--bg);
      color: var(--text);
      margin: 0;
    }

    button,
    input,
    select,
    textarea {
      font: inherit;
    }

    .app {
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 100vh;
    }

    .topbar {
      align-items: center;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      display: flex;
      gap: 20px;
      justify-content: space-between;
      padding: 16px 22px;
      position: sticky;
      top: 0;
      z-index: 20;
    }

    .title {
      display: grid;
      gap: 4px;
    }

    .title h1 {
      font-size: 20px;
      line-height: 1.2;
      margin: 0;
    }

    .title p {
      color: var(--muted);
      font-size: 13px;
      margin: 0;
    }

    .setup-guidance {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
      max-width: 720px;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }

    .button {
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--border-strong);
      border-radius: 6px;
      color: var(--text);
      cursor: pointer;
      display: inline-flex;
      font-weight: 650;
      min-height: 38px;
      padding: 8px 12px;
    }

    .button:hover:not(:disabled) {
      border-color: var(--accent);
      color: var(--accent-strong);
    }

    .button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #ffffff;
    }

    .button.primary:hover:not(:disabled) {
      background: var(--accent-strong);
      color: #ffffff;
    }

    .button.danger {
      border-color: #fecdca;
      color: var(--danger);
    }

    .button.danger:hover:not(:disabled) {
      background: #fef3f2;
      border-color: #fda29b;
      color: var(--danger);
    }

    .button:disabled {
      cursor: not-allowed;
      opacity: 0.45;
    }

    .layout {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 0;
      width: 100%;
    }

    .sidebar {
      background: var(--panel);
      border-right: 1px solid var(--border);
      padding: 18px 16px;
    }

    .search {
      display: grid;
      gap: 6px;
      margin-bottom: 18px;
    }

    .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }

    .input,
    .textarea,
    .select {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      min-height: 38px;
      outline: none;
      padding: 8px 10px;
      width: 100%;
    }

    .checkbox-control {
      align-items: center;
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 6px;
      display: inline-flex;
      gap: 10px;
      min-height: 38px;
      padding: 8px 10px;
      width: fit-content;
    }

    .checkbox-control input {
      height: 16px;
      width: 16px;
    }

    .checkbox-control span {
      font-size: 13px;
      font-weight: 650;
    }

    .textarea {
      line-height: 1.45;
      min-height: 108px;
      resize: vertical;
    }

    .textarea.large {
      min-height: 260px;
    }

    .response-editor {
      display: grid;
      gap: 12px;
    }

    .response-card {
      border: 1px solid var(--border);
      border-radius: 8px;
      display: grid;
      gap: 8px;
      padding: 10px;
    }

    .response-card__header {
      align-items: center;
      display: flex;
      gap: 8px;
      justify-content: space-between;
    }

    .response-card__title {
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      text-transform: uppercase;
    }

    .response-card .textarea {
      min-height: 220px;
    }

    .response-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-start;
    }

    .input:focus,
    .textarea:focus,
    .select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
    }

    .tabs {
      display: grid;
      gap: 8px;
    }

    .tab {
      background: transparent;
      border: 1px solid transparent;
      border-radius: 6px;
      color: var(--text);
      cursor: pointer;
      display: grid;
      gap: 4px;
      padding: 10px;
      text-align: left;
      width: 100%;
    }

    .tab:hover,
    .tab.active {
      background: var(--panel-strong);
      border-color: var(--border);
    }

    .tab.review-tab {
      border-color: var(--border);
      margin-top: 8px;
    }

    .tab-title {
      align-items: center;
      display: flex;
      font-weight: 750;
      gap: 8px;
      justify-content: space-between;
    }

    .tab-meta {
      color: var(--muted);
      font-size: 12px;
    }

    .badge {
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      padding: 2px 8px;
      white-space: nowrap;
    }

    .badge.changed {
      background: #ecfdf3;
      border-color: #abefc6;
      color: var(--success);
    }

    .main {
      display: grid;
      gap: 16px;
      justify-self: stretch;
      padding: 20px 24px 28px;
      width: 100%;
    }

    .content-grid {
      align-items: start;
      display: grid;
      gap: 16px;
      grid-template-columns: minmax(760px, 930px) minmax(300px, 360px);
      justify-content: start;
      max-width: 1320px;
      width: 100%;
    }

    .editor-column {
      display: grid;
      gap: 16px;
      min-width: 0;
    }

    .preview-panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: none;
      padding: 14px 16px;
    }

    .preview-panel {
      display: grid;
      gap: 12px;
      position: sticky;
      top: 86px;
    }

    .preview-title {
      display: grid;
      gap: 4px;
    }

    .preview-title h2 {
      font-size: 16px;
      margin: 0;
    }

    .preview-title p {
      color: var(--muted);
      font-size: 13px;
      margin: 0;
    }

    .preview-list {
      display: grid;
      gap: 8px;
    }

    .preview-item {
      border: 1px solid var(--border);
      border-radius: 6px;
      display: grid;
      gap: 5px;
      padding: 10px;
    }

    .preview-label {
      color: var(--muted);
      font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      font-size: 11px;
      overflow-wrap: anywhere;
    }

    .preview-value {
      font-size: 13px;
      line-height: 1.45;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }

    .mock-preview {
      display: grid;
      gap: 10px;
    }

    .mock-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 8px;
      display: grid;
      gap: 8px;
      padding: 12px;
    }

    .mock-label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    .mock-title {
      color: var(--text);
      font-size: 15px;
      font-weight: 800;
      line-height: 1.25;
    }

    .mock-text {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      margin: 0;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }

    .mock-chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .mock-chip {
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 999px;
      color: var(--text);
      font-size: 11px;
      font-weight: 700;
      padding: 4px 8px;
    }

    .mock-chip.inactive {
      color: var(--muted);
      text-decoration: line-through;
    }

    .mock-nav {
      align-items: center;
      display: flex;
      gap: 8px;
      justify-content: space-between;
    }

    .mock-nav-links {
      display: flex;
      gap: 8px;
    }

    .mock-nav-link {
      background: var(--panel-strong);
      border-radius: 999px;
      height: 7px;
      width: 34px;
    }

    .mock-home-grid {
      display: grid;
      gap: 8px;
      grid-template-columns: 1fr 1fr;
    }

    .mock-project-items {
      display: grid;
      gap: 8px;
    }

    .mock-prompt {
      border: 1px solid var(--border);
      border-radius: 999px;
      color: var(--text);
      font-size: 12px;
      font-weight: 700;
      overflow-wrap: anywhere;
      padding: 7px 10px;
    }

    .mock-disclaimer h3 {
      font-size: 13px;
      margin: 0;
    }

    .mock-disclaimer p {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      margin: 0;
    }

    .summary-band {
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: var(--shadow);
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      justify-content: space-between;
      padding: 14px 16px;
    }

    .status-line {
      color: var(--muted);
      font-size: 14px;
    }

    .status-line strong {
      color: var(--text);
    }

    .section-heading {
      display: grid;
      gap: 4px;
    }

    .section-heading h2 {
      font-size: 18px;
      margin: 0;
    }

    .section-heading p {
      color: var(--muted);
      margin: 0;
    }

    .fields {
      display: grid;
      gap: 12px;
    }

    .fields.hidden {
      display: none;
    }

    .field {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      display: grid;
      gap: 10px;
      padding: 14px;
    }

    .field.changed {
      border-color: #12b76a;
      box-shadow: inset 3px 0 0 #12b76a;
    }

    .field-pair {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      display: grid;
      gap: 12px;
      padding: 14px;
    }

    .field-group {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: var(--shadow);
      display: grid;
      gap: 12px;
      padding: 16px;
    }

    .field-group__header {
      display: grid;
      gap: 4px;
    }

    .field-group__header h3 {
      font-size: 15px;
      margin: 0;
    }

    .field-group__header p {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      margin: 0;
    }

    .field-group__body {
      display: grid;
      gap: 12px;
    }

    .pair-title {
      color: var(--text);
      font-size: 14px;
      font-weight: 750;
    }

    .pair-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }

    .field-pair.preview-item-pair .pair-grid {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    }

    .field-pair.preview-item-pair .field[data-path$=".detail"] {
      grid-column: 1 / -1;
    }

    .field-header {
      align-items: start;
      display: flex;
      gap: 12px;
      justify-content: space-between;
    }

    .field-heading {
      display: grid;
      gap: 4px;
      min-width: 0;
    }

    .field-label {
      font-size: 14px;
      font-weight: 750;
      line-height: 1.3;
    }

    .field-path {
      color: var(--muted);
      font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      font-size: 11px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .field-type {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .help {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      margin: 0;
    }

    .system-preview {
      background: #f8fafc;
      border: 1px dashed var(--border);
      border-radius: 6px;
      color: var(--text);
      font-family: inherit;
      font-size: 12px;
      line-height: 1.45;
      margin: 0;
      overflow-wrap: anywhere;
      padding: 10px;
      white-space: pre-wrap;
    }

    .review {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: var(--shadow);
      display: none;
      gap: 14px;
      padding: 16px;
    }

    .review.visible {
      display: grid;
    }

    .review h2,
    .review h3 {
      margin: 0;
    }

    .review-list {
      display: grid;
      gap: 8px;
    }

    .review-item {
      border: 1px solid var(--border);
      border-radius: 6px;
      display: grid;
      gap: 6px;
      padding: 10px;
    }

    .review-path {
      font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
      font-weight: 700;
    }

    .diff-grid {
      display: grid;
      gap: 8px;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    }

    .diff-box {
      background: var(--panel-strong);
      border-radius: 6px;
      color: var(--text);
      font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
      min-height: 42px;
      overflow: auto;
      padding: 8px;
      white-space: pre-wrap;
    }

    .notice {
      border-radius: 6px;
      display: none;
      line-height: 1.45;
      padding: 10px 12px;
    }

    .notice.visible {
      display: block;
    }

    .notice.success {
      background: #ecfdf3;
      color: var(--success);
    }

    .notice.warning {
      background: #fffaeb;
      color: var(--warning);
    }

    .notice.danger {
      background: #fef3f2;
      color: var(--danger);
    }

    .output {
      background: #101828;
      border-radius: 6px;
      color: #f9fafb;
      display: none;
      font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
      max-height: 280px;
      overflow: auto;
      padding: 12px;
      white-space: pre-wrap;
    }

    .output.visible {
      display: block;
    }

    .empty {
      background: var(--panel);
      border: 1px dashed var(--border-strong);
      border-radius: 8px;
      color: var(--muted);
      padding: 24px;
      text-align: center;
    }

    @media (max-width: 900px) {
      .layout {
        grid-template-columns: 1fr;
      }

      .content-grid {
        grid-template-columns: 1fr;
        max-width: none;
      }

      .preview-panel {
        position: static;
      }

      .sidebar {
        border-bottom: 1px solid var(--border);
        border-right: 0;
        position: static;
      }

      .tabs {
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }

      .topbar {
        align-items: stretch;
        flex-direction: column;
      }

      .actions {
        justify-content: flex-start;
      }
    }

    @media (max-width: 640px) {
      .diff-grid,
      .field-pair.preview-item-pair .pair-grid,
      .mock-home-grid,
      .pair-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="title">
        <h1>Project Setup Wizard</h1>
        <p id="config-path">Loading config...</p>
      </div>
      <div class="setup-guidance">
        Go through each menu item, adjust the values you need, then open Review & Save to check the diff and validate before saving.
      </div>
      <div class="actions">
        <button class="button" id="discard-button" type="button">Discard unsaved changes</button>
        <button class="button danger" id="close-button" type="button">Finish setup</button>
      </div>
    </header>
    <div class="layout">
      <aside class="sidebar">
        <label class="search">
          <span class="label">Search fields</span>
          <input class="input" id="search-input" placeholder="Path or value" type="search">
        </label>
        <nav class="tabs" id="tabs"></nav>
      </aside>
      <main class="main">
        <div class="content-grid">
          <div class="editor-column">
            <section class="summary-band">
              <div class="section-heading">
                <h2 id="section-title">Loading</h2>
                <p id="section-description">Reading current project config values.</p>
              </div>
              <div class="status-line" id="change-summary"><strong>0</strong> changed fields</div>
            </section>
            <section class="fields" id="fields"></section>
            <section class="review" id="review-panel">
              <div class="section-heading">
                <h2>Review & Save</h2>
                <p>Saving is disabled until the current changes pass validation.</p>
              </div>
              <div class="notice" id="review-notice"></div>
              <div class="review-list" id="review-list"></div>
              <div class="actions">
                <button class="button primary" id="validate-button" type="button">Validate changes</button>
                <button class="button primary" disabled id="save-button" type="button">Save validated changes</button>
              </div>
              <pre class="output" id="validation-output"></pre>
              <div>
                <h3>Follow-up actions</h3>
                <div class="review-list" id="follow-up-list"></div>
              </div>
            </section>
          </div>
          <aside class="preview-panel">
            <div class="preview-title">
              <h2>Section preview</h2>
              <p id="preview-description">Current values for the selected section.</p>
            </div>
            <div class="preview-list" id="preview-list"></div>
          </aside>
        </div>
      </main>
    </div>
  </div>
  <script>
    window.__WIZARD_TOKEN__ = ${encodedToken};
  </script>
  <script>
    const token = window.__WIZARD_TOKEN__;
    const REVIEW_SECTION_ID = "__review__";
    const state = {
      activeSectionId: "",
      fields: [],
      followUpActions: [],
      sections: [],
      values: new Map(),
      validationKey: null,
      validatedAssignmentsKey: "",
    };

    const elements = {
      changeSummary: document.getElementById("change-summary"),
      closeButton: document.getElementById("close-button"),
      configPath: document.getElementById("config-path"),
      discardButton: document.getElementById("discard-button"),
      fields: document.getElementById("fields"),
      followUpList: document.getElementById("follow-up-list"),
      previewDescription: document.getElementById("preview-description"),
      previewList: document.getElementById("preview-list"),
      reviewList: document.getElementById("review-list"),
      reviewNotice: document.getElementById("review-notice"),
      reviewPanel: document.getElementById("review-panel"),
      saveButton: document.getElementById("save-button"),
      searchInput: document.getElementById("search-input"),
      sectionDescription: document.getElementById("section-description"),
      sectionTitle: document.getElementById("section-title"),
      tabs: document.getElementById("tabs"),
      validateButton: document.getElementById("validate-button"),
      validationOutput: document.getElementById("validation-output"),
    };

    elements.closeButton.addEventListener("click", closeWizard);
    elements.discardButton.addEventListener("click", discardUnsavedChanges);
    elements.validateButton.addEventListener("click", validateChanges);
    elements.saveButton.addEventListener("click", saveChanges);
    elements.searchInput.addEventListener("input", renderFields);

    loadState().catch((error) => showTopError(error.message));

    async function loadState() {
      clearValidation();
      const response = await apiGet("/api/state");
      state.sections = response.sections;
      state.fields = response.fields;
      state.followUpActions = response.followUpActions;
      state.values = new Map(
        response.fields.map((field) => [field.path, serialiseValue(field)]),
      );
      if (
        state.activeSectionId !== REVIEW_SECTION_ID &&
        !state.sections.some((section) => section.id === state.activeSectionId)
      ) {
        state.activeSectionId = state.sections[0]?.id ?? "";
      }
      elements.configPath.textContent = response.configPath;
      renderTabs();
      renderFields();
      renderFollowUps();
    }

    async function discardUnsavedChanges() {
      if (getAssignments().length > 0 && !window.confirm("Discard all unsaved changes?")) {
        return;
      }

      await loadState();
    }

    async function closeWizard() {
      if (getAssignments().length > 0 && !window.confirm("Finish setup and discard unsaved changes?")) {
        return;
      }

      try {
        await apiPost("/api/shutdown", {});
      } catch {
        // The local server may close before the browser finishes reading the response.
      }

      document.body.innerHTML = '<main style="font-family: system-ui, sans-serif; padding: 32px;"><h1>Wizard closed</h1><p>The local setup wizard server has been stopped. You can close this tab.</p></main>';
    }

    function renderTabs() {
      elements.tabs.textContent = "";

      for (const section of state.sections) {
        const button = document.createElement("button");
        button.className = "tab";
        button.type = "button";
        if (section.id === state.activeSectionId) {
          button.classList.add("active");
        }

        const title = document.createElement("span");
        title.className = "tab-title";
        title.textContent = section.title;

        const badge = document.createElement("span");
        badge.className = "badge";
        const changedCount = getAssignments().filter((assignment) =>
          getField(assignment.path)?.sectionId === section.id,
        ).length;
        if (changedCount > 0) {
          badge.classList.add("changed");
          badge.textContent = String(changedCount);
        } else {
          badge.textContent = String(section.fieldCount);
        }
        title.appendChild(badge);

        const meta = document.createElement("span");
        meta.className = "tab-meta";
        meta.textContent = section.description;

        button.append(title, meta);
        button.addEventListener("click", () => {
          state.activeSectionId = section.id;
          renderTabs();
          renderFields();
        });
        elements.tabs.appendChild(button);
      }

      const reviewButton = document.createElement("button");
      reviewButton.className = "tab review-tab";
      reviewButton.type = "button";
      if (state.activeSectionId === REVIEW_SECTION_ID) {
        reviewButton.classList.add("active");
      }

      const reviewTitle = document.createElement("span");
      reviewTitle.className = "tab-title";
      reviewTitle.textContent = "Review & Save";

      const reviewBadge = document.createElement("span");
      reviewBadge.className = "badge";
      const changeCount = getAssignments().length;
      if (changeCount > 0) {
        reviewBadge.classList.add("changed");
      }
      reviewBadge.textContent = String(changeCount);
      reviewTitle.appendChild(reviewBadge);

      const reviewMeta = document.createElement("span");
      reviewMeta.className = "tab-meta";
      reviewMeta.textContent = "Validate changes before writing config";

      reviewButton.append(reviewTitle, reviewMeta);
      reviewButton.addEventListener("click", () => {
        state.activeSectionId = REVIEW_SECTION_ID;
        renderTabs();
        showReview();
      });
      elements.tabs.appendChild(reviewButton);
    }

    function renderFields() {
      if (state.activeSectionId === REVIEW_SECTION_ID) {
        showReview();
        return;
      }

      const section = state.sections.find((item) => item.id === state.activeSectionId);
      const query = elements.searchInput.value.trim().toLowerCase();
      const fields = state.fields.filter((field) => {
        if (field.sectionId !== state.activeSectionId) {
          return false;
        }
        if (!isFieldVisible(field)) {
          return false;
        }
        if (!query) {
          return true;
        }
        return (
          field.path.toLowerCase().includes(query) ||
          field.label.toLowerCase().includes(query) ||
          field.description.toLowerCase().includes(query) ||
          serialiseValue(field).toLowerCase().includes(query)
        );
      });

      elements.sectionTitle.textContent = section?.title ?? "Project config";
      elements.sectionDescription.textContent = section
        ? section.description
        : "Select a section.";
      elements.fields.textContent = "";
      elements.fields.classList.remove("hidden");
      elements.reviewPanel.classList.remove("visible");

      if (fields.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No fields match the current filter.";
        elements.fields.appendChild(empty);
        renderPreview(section, fields);
        updateSummary();
        return;
      }

      for (const item of groupFieldsForRendering(fields)) {
        elements.fields.appendChild(renderRenderableItem(item));
      }

      renderPreview(section, fields);
      updateSummary();
    }

    function isFieldVisible(field) {
      return Boolean(field);
    }

    function renderField(field) {
      const wrapper = document.createElement("article");
      wrapper.className = "field";
      wrapper.dataset.path = field.path;

      const header = document.createElement("div");
      header.className = "field-header";

      const heading = document.createElement("div");
      heading.className = "field-heading";

      const label = document.createElement("div");
      label.className = "field-label";
      label.textContent = field.label;

      const path = document.createElement("div");
      path.className = "field-path";
      path.textContent = field.path;
      heading.append(label, path);

      const type = document.createElement("div");
      type.className = "field-type";
      type.textContent = field.type;
      header.append(heading, type);

      const description = document.createElement("p");
      description.className = "help";
      description.textContent = field.description;

      const control = createControl(field);
      const example = document.createElement("p");
      example.className = "help";

      wrapper.append(header, description, control);
      if (field.options || field.example) {
        example.textContent = field.options
          ? "Options: " + field.options.join(", ")
          : "Example: " + field.example;
        wrapper.appendChild(example);
      }
      if (field.readonlyPreview) {
        const preview = document.createElement("pre");
        preview.className = "system-preview";
        preview.textContent = field.readonlyPreview;
        wrapper.appendChild(preview);
      }
      updateFieldChangedState(wrapper, field);
      return wrapper;
    }

    function renderRenderableItem(item) {
      if (item.kind === "group") {
        return renderFieldGroup(item);
      }
      if (item.kind === "pair") {
        return renderFieldPair(item);
      }
      return renderField(item.field);
    }

    function renderFieldGroup(item) {
      const wrapper = document.createElement("section");
      wrapper.className = "field-group";

      const header = document.createElement("div");
      header.className = "field-group__header";

      const title = document.createElement("h3");
      title.textContent = item.label;

      const description = document.createElement("p");
      description.textContent = item.description;

      const body = document.createElement("div");
      body.className = "field-group__body";

      for (const child of groupPairFieldsForRendering(item.fields)) {
        body.appendChild(renderRenderableItem(child));
      }

      header.append(title, description);
      wrapper.append(header, body);
      return wrapper;
    }

    function renderFieldPair(item) {
      const wrapper = document.createElement("article");
      wrapper.className = "field-pair";
      if (item.value?.startsWith("home-featured-preview-item-")) {
        wrapper.classList.add("preview-item-pair");
      }

      const title = document.createElement("div");
      title.className = "pair-title";
      title.textContent = item.label;

      const grid = document.createElement("div");
      grid.className = "pair-grid";

      for (const field of item.fields) {
        grid.appendChild(renderField(field));
      }

      wrapper.append(title, grid);
      return wrapper;
    }

    function groupFieldsForRendering(fields) {
      const items = [];
      const handledGroups = new Set();

      for (const field of fields) {
        if (!field.group) {
          continue;
        }
        if (handledGroups.has(field.group.value)) {
          continue;
        }

        const groupFields = fields.filter(
          (candidate) => candidate.group?.value === field.group.value,
        );
        handledGroups.add(field.group.value);
        items.push({
          description: field.group.description,
          fields: groupFields,
          kind: "group",
          label: field.group.label,
        });
      }

      const ungroupedFields = fields.filter((field) => !field.group);
      items.push(...groupPairFieldsForRendering(ungroupedFields));
      return items;
    }

    function groupPairFieldsForRendering(fields) {
      const items = [];
      const handledPairGroups = new Set();

      for (const field of fields) {
        if (!field.pairGroup) {
          items.push({ field, kind: "field" });
          continue;
        }

        if (handledPairGroups.has(field.pairGroup.value)) {
          continue;
        }

        const pairFields = fields
          .filter((candidate) => candidate.pairGroup?.value === field.pairGroup.value)
          .sort((left, right) => left.pairGroup.order - right.pairGroup.order);

        handledPairGroups.add(field.pairGroup.value);
        items.push({
          fields: pairFields,
          kind: "pair",
          label: field.pairGroup.label,
          value: field.pairGroup.value,
        });
      }

      return items;
    }

    function createControl(field) {
      const value = state.values.get(field.path) ?? serialiseValue(field);

      if (/^chat\.quickPrompts\[\d+\]\.responses$/.test(field.path)) {
        return createResponsesControl(field);
      }

      if (Array.isArray(field.options) && field.options.length > 0) {
        const select = document.createElement("select");
        select.className = "select";
        for (const optionValue of field.options) {
          const option = document.createElement("option");
          option.value = optionValue;
          option.textContent = optionValue;
          select.appendChild(option);
        }
        select.value = value;
        select.addEventListener("change", () => updateValue(field.path, select.value));
        return select;
      }

      if (field.type === "boolean") {
        const label = document.createElement("label");
        label.className = "checkbox-control";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = value === "true";

        const text = document.createElement("span");
        text.textContent = getBooleanDisplayLabel(field.path, checkbox.checked);

        checkbox.addEventListener("change", () => {
          text.textContent = getBooleanDisplayLabel(field.path, checkbox.checked);
          updateValue(field.path, checkbox.checked ? "true" : "false");
        });

        label.append(checkbox, text);
        return label;
      }

      if (field.type === "number") {
        const input = document.createElement("input");
        input.className = "input";
        input.type = "number";
        input.value = value;
        input.addEventListener("input", () => updateValue(field.path, input.value));
        return input;
      }

      if (field.type === "array" || value.length > 100 || value.includes("\\n")) {
        const textarea = document.createElement("textarea");
        textarea.className = "textarea";
        if (field.path === "disclaimer.bodyMarkdown") {
          textarea.classList.add("large");
        }
        textarea.spellcheck = false;
        textarea.value = value;
        textarea.addEventListener("input", () => updateValue(field.path, textarea.value));
        return textarea;
      }

      const input = document.createElement("input");
      input.className = "input";
      input.type = "text";
      input.value = value;
      input.addEventListener("input", () => updateValue(field.path, input.value));
      return input;
    }

    function createResponsesControl(field) {
      const wrapper = document.createElement("div");
      wrapper.className = "response-editor";

      function getResponses() {
        const rawValue = state.values.get(field.path) ?? serialiseValue(field);
        try {
          const parsedValue = JSON.parse(rawValue);
          return Array.isArray(parsedValue) && parsedValue.every((item) => typeof item === "string")
            ? parsedValue
            : [String(rawValue)];
        } catch {
          return [String(rawValue)];
        }
      }

      function setResponses(nextResponses) {
        const cleanedResponses = nextResponses.map((item) => String(item));
        updateValue(field.path, JSON.stringify(cleanedResponses, null, 2));
      }

      function renderResponses() {
        wrapper.textContent = "";
        const responses = getResponses();

        responses.forEach((response, index) => {
          const card = document.createElement("article");
          card.className = "response-card";

          const header = document.createElement("div");
          header.className = "response-card__header";

          const title = document.createElement("div");
          title.className = "response-card__title";
          title.textContent = "Response variant " + (index + 1);

          const removeButton = document.createElement("button");
          removeButton.className = "button danger";
          removeButton.type = "button";
          removeButton.textContent = "Remove";
          removeButton.disabled = responses.length <= 1;
          removeButton.addEventListener("click", () => {
            const nextResponses = getResponses();
            nextResponses.splice(index, 1);
            setResponses(nextResponses);
            renderResponses();
          });

          const textarea = document.createElement("textarea");
          textarea.className = "textarea";
          textarea.spellcheck = false;
          textarea.value = response;
          textarea.addEventListener("input", () => {
            const nextResponses = getResponses();
            nextResponses[index] = textarea.value;
            setResponses(nextResponses);
          });

          header.append(title, removeButton);
          card.append(header, textarea);
          wrapper.appendChild(card);
        });

        const actions = document.createElement("div");
        actions.className = "response-actions";

        const addButton = document.createElement("button");
        addButton.className = "button";
        addButton.type = "button";
        addButton.textContent = "Add response";
        addButton.addEventListener("click", () => {
          const nextResponses = getResponses();
          nextResponses.push("");
          setResponses(nextResponses);
          renderResponses();
        });

        actions.appendChild(addButton);
        wrapper.appendChild(actions);
      }

      renderResponses();
      return wrapper;
    }

    function updateValue(path, value) {
      state.values.set(path, value);
      clearValidation();

      const field = getField(path);
      const fieldNode = document.querySelector(\`.field[data-path="\${cssEscape(path)}"]\`);
      if (field && fieldNode) {
        updateFieldChangedState(fieldNode, field);
      }

      renderTabs();
      renderPreview(
        state.sections.find((item) => item.id === state.activeSectionId),
        state.fields.filter(
          (field) =>
            field.sectionId === state.activeSectionId &&
            isFieldVisible(field),
        ),
      );
      updateSummary();
    }

    function updateFieldChangedState(wrapper, field) {
      const changed = isChanged(field);
      wrapper.classList.toggle("changed", changed);
    }

    function updateSummary() {
      const count = getAssignments().length;
      elements.changeSummary.innerHTML = \`<strong>\${count}</strong> changed field\${count === 1 ? "" : "s"}\`;
    }

    function renderPreview(section, visibleFields) {
      elements.previewList.textContent = "";

      if (state.activeSectionId === REVIEW_SECTION_ID) {
        elements.previewDescription.textContent = "Changed values waiting for validation.";
        const assignments = getAssignments();

        if (assignments.length === 0) {
          appendPreviewItem("No changes", "Open a section and edit values before saving.");
          return;
        }

        for (const assignment of assignments.slice(0, 8)) {
          const field = getField(assignment.path);
          appendPreviewItem(
            field?.label ?? assignment.path,
            formatDisplayValue(field, assignment.rawValue),
          );
        }
        return;
      }

      elements.previewDescription.textContent = section
        ? "Approximate public output for " + section.title + "."
        : "Current values for the selected section.";

      if (section?.id === "siteIdentity") {
        renderSiteIdentityPreview();
        return;
      }

      if (section?.id === "homePage") {
        renderHomePagePreview();
        return;
      }

      if (section?.id === "chatSettings") {
        renderChatPreview();
        return;
      }

      if (section?.id === "resumePdf") {
        renderResumePreview();
        return;
      }

      if (section?.id === "disclaimerPage") {
        renderDisclaimerPreview();
        return;
      }

      const previewFields = selectPreviewFields(section?.id, visibleFields);
      if (previewFields.length === 0) {
        appendPreviewItem("No preview", "Select a section to see current values.");
        return;
      }

      for (const field of previewFields) {
        appendPreviewItem(
          field.label,
          formatDisplayValue(field, state.values.get(field.path) ?? serialiseValue(field)),
        );
      }
    }

    function renderSiteIdentityPreview() {
      const root = createPreviewRoot();
      const siteName = getPathText("site.name", "example.com");
      const canonicalUrl = getPathText("site.canonicalUrl", "https://example.com");
      const displayName = getPathText("owner.displayName", "Your Name");
      const roleTitle = getPathText("owner.roleTitle", "Software Developer");
      const defaultTitle = getPathText("seo.defaultTitle", displayName);
      const description = getPathText("seo.description", "Main SEO description.");

      const header = appendMockCard(root);
      const nav = document.createElement("div");
      nav.className = "mock-nav";

      const brand = document.createElement("div");
      brand.className = "mock-title";
      brand.textContent = siteName;

      const navLinks = document.createElement("div");
      navLinks.className = "mock-nav-links";
      navLinks.append(mockNavLine(), mockNavLine(), mockNavLine());
      nav.append(brand, navLinks);

      const owner = document.createElement("p");
      owner.className = "mock-text";
      owner.textContent = displayName + " - " + roleTitle;
      header.append(nav, owner);

      appendMockCard(root, {
        label: "Browser title",
        text: defaultTitle,
      });
      appendMockCard(root, {
        label: "Canonical URL",
        text: canonicalUrl,
      });
      appendMockCard(root, {
        label: "Search description",
        text: compactText(description, 260),
      });
      appendLinkChips(root, ["github", "linkedin", "facebook"]);
    }

    function renderHomePagePreview() {
      const root = createPreviewRoot();
      const profileName = getPathText("home.profileCard.name", getPathText("owner.displayName", "Your Name"));
      const profileSummary = getPathText("home.profileCard.summary", "Profile summary.");
      const featuredTitle = getPathText("home.featuredProject.title", "Featured project");
      const featuredDescription = getPathText("home.featuredProject.description", "Project description.");
      const projectStack = getPathArray("home.projectStack").slice(0, 8);

      const topGrid = document.createElement("div");
      topGrid.className = "mock-home-grid";
      const profile = appendMockCard(topGrid, {
        label: "Profile card",
        text: compactText(profileSummary, 180),
        title: profileName,
      });
      const connect = appendMockCard(topGrid, {
        label: "Connect",
        title: "Public links",
      });
      appendVisibilityChips(connect, "home.connectCard.linkVisibility", ["github", "linkedin", "facebook"]);
      root.appendChild(topGrid);

      const featured = appendMockCard(root, {
        label: getPathText("home.featuredProject.previewHeading", "Featured project"),
        text: compactText(formatPreviewText(featuredDescription), 220),
        title: featuredTitle,
      });
      const cta = document.createElement("div");
      cta.className = "mock-chip-row";
      cta.appendChild(mockChip(getPathText("home.featuredProject.cta", "Open project")));
      featured.appendChild(cta);

      const items = document.createElement("div");
      items.className = "mock-project-items";
      for (let index = 0; index < 3; index += 1) {
        appendMockCard(items, {
          label: "Preview item " + (index + 1),
          text: compactText(
            getPathText("home.featuredProject.previewItems[" + index + "].detail", ""),
            120,
          ),
          title: getPathText("home.featuredProject.previewItems[" + index + "].title", ""),
        });
      }
      root.appendChild(items);

      if (projectStack.length > 0) {
        const stack = appendMockCard(root, {
          label: getPathText("home.projectStackTitle", "Project stack"),
        });
        const chips = document.createElement("div");
        chips.className = "mock-chip-row";
        for (const item of projectStack) {
          chips.appendChild(mockChip(item));
        }
        stack.appendChild(chips);
      }
    }

    function renderChatPreview() {
      const root = createPreviewRoot();
      const promptCard = appendMockCard(root, {
        label: "Quick prompts",
        title: "Chat shortcuts",
      });

      for (let index = 0; index < 3; index += 1) {
        const prompt = document.createElement("div");
        prompt.className = "mock-prompt";
        prompt.textContent = getPathText("chat.quickPrompts[" + index + "].label", "Quick prompt");
        promptCard.appendChild(prompt);
      }

      const firstResponses = getPathArray("chat.quickPrompts[0].responses");
      appendMockCard(root, {
        label: "Example scripted answer",
        text: firstResponses.length > 0 ? compactText(firstResponses[0], 360) : "No response variants configured.",
      });

      const languageCard = appendMockCard(root, {
        label: "Language restrictions",
        title: "System fallback switches",
      });
      appendVisibilityChips(languageCard, "chat.languageRestrictions", [
        "russian",
        "ukrainian",
        "otherNonEnglish",
      ]);
    }

    function renderResumePreview() {
      const root = createPreviewRoot();
      const pageHeading = getPathText("resume.pageHeading", getPathText("owner.displayName", "Your Name"));
      const displayName = getPathText("resume.pdf.displayName", pageHeading);
      const roleTitle = getPathText("owner.roleTitle", "Software Developer");
      const filename = getPathText("resume.downloadFileNameBase", "resume");

      const page = appendMockCard(root, {
        label: "Resume page",
        text: "Download filename: " + filename + ".pdf",
        title: pageHeading,
      });
      const buttonRow = document.createElement("div");
      buttonRow.className = "mock-chip-row";
      buttonRow.appendChild(mockChip("Download PDF"));
      page.appendChild(buttonRow);

      const pdf = appendMockCard(root, {
        label: "PDF header",
        text: roleTitle,
        title: displayName,
      });
      appendVisibilityChips(pdf, "resume.pdf.headerLinkVisibility", [
        "website",
        "linkedin",
        "github",
        "facebook",
        "rightToWorkUk",
      ]);
    }

    function renderDisclaimerPreview() {
      const root = createPreviewRoot();
      const title = getPathText("disclaimer.title", "Disclaimer");
      const body = getPathText("disclaimer.bodyMarkdown", "");
      const card = appendMockCard(root, {
        label: "Public page",
        title,
      });
      card.classList.add("mock-disclaimer");

      const blocks = parseMarkdownPreviewBlocks(body).slice(0, 5);
      if (blocks.length === 0) {
        const empty = document.createElement("p");
        empty.textContent = "No disclaimer text configured.";
        card.appendChild(empty);
        return;
      }

      for (const block of blocks) {
        if (block.kind === "heading") {
          const heading = document.createElement("h3");
          heading.textContent = block.text;
          card.appendChild(heading);
          continue;
        }

        const paragraph = document.createElement("p");
        paragraph.textContent = compactText(block.text, 180);
        card.appendChild(paragraph);
      }
    }

    function createPreviewRoot() {
      const root = document.createElement("div");
      root.className = "mock-preview";
      elements.previewList.appendChild(root);
      return root;
    }

    function appendMockCard(parent, content = {}) {
      const card = document.createElement("article");
      card.className = "mock-card";

      if (content.label) {
        const label = document.createElement("div");
        label.className = "mock-label";
        label.textContent = content.label;
        card.appendChild(label);
      }

      if (content.title) {
        const title = document.createElement("div");
        title.className = "mock-title";
        title.textContent = content.title;
        card.appendChild(title);
      }

      if (content.text) {
        const text = document.createElement("p");
        text.className = "mock-text";
        text.textContent = content.text;
        card.appendChild(text);
      }

      parent.appendChild(card);
      return card;
    }

    function appendLinkChips(parent, keys) {
      const card = appendMockCard(parent, {
        label: "Public links",
      });
      const chips = document.createElement("div");
      chips.className = "mock-chip-row";

      for (const key of keys) {
        const value = getPathText("links." + key, "");
        chips.appendChild(mockChip(humanisePathToken(key), !value));
      }

      card.appendChild(chips);
    }

    function appendVisibilityChips(parent, basePath, keys) {
      const chips = document.createElement("div");
      chips.className = "mock-chip-row";

      for (const key of keys) {
        const active = getPathBoolean(basePath + "." + key + ".enabled") ||
          getPathBoolean(basePath + "." + key);
        chips.appendChild(mockChip(humanisePathToken(key), !active));
      }

      parent.appendChild(chips);
    }

    function mockChip(text, inactive = false) {
      const chip = document.createElement("span");
      chip.className = inactive ? "mock-chip inactive" : "mock-chip";
      chip.textContent = text;
      return chip;
    }

    function mockNavLine() {
      const line = document.createElement("span");
      line.className = "mock-nav-link";
      return line;
    }

    function getPathText(path, fallback = "") {
      const field = getField(path);
      if (!field) {
        return fallback;
      }

      const rawValue = state.values.get(path) ?? serialiseValue(field);
      if (field.type === "array") {
        return formatPreviewText(getPathArray(path));
      }
      return String(rawValue || fallback);
    }

    function getPathArray(path) {
      const field = getField(path);
      if (!field) {
        return [];
      }

      const rawValue = state.values.get(path) ?? serialiseValue(field);
      try {
        const parsedValue = JSON.parse(rawValue);
        return Array.isArray(parsedValue) ? parsedValue.map((item) => String(item)) : [];
      } catch {
        return [];
      }
    }

    function getPathBoolean(path) {
      const field = getField(path);
      if (!field) {
        return false;
      }

      return (state.values.get(path) ?? serialiseValue(field)) === "true";
    }

    function formatPreviewText(value) {
      if (Array.isArray(value)) {
        return value.join("\\n");
      }
      return String(value ?? "");
    }

    function compactText(value, maxLength) {
      const normalized = formatPreviewText(value).replace(/\\s+/g, " ").trim();
      if (normalized.length <= maxLength) {
        return normalized;
      }
      return normalized.slice(0, maxLength - 1).trimEnd() + "...";
    }

    function parseMarkdownPreviewBlocks(markdown) {
      const blocks = [];
      for (const rawLine of markdown.split("\\n")) {
        const line = rawLine.trim();
        if (!line) {
          continue;
        }
        if (line.startsWith("## ")) {
          blocks.push({
            kind: "heading",
            text: line.replace(/^#+\\s+/, ""),
          });
          continue;
        }
        if (!line.startsWith("#") && !line.startsWith("- ")) {
          blocks.push({
            kind: "paragraph",
            text: line,
          });
        }
      }
      return blocks;
    }

    function selectPreviewFields(sectionId, fields) {
      const preferredPathsBySection = {
        chatSettings: [
          "chat.quickPrompts[0].label",
          "chat.quickPrompts[0].responses",
          "chat.languageRestrictions.russian.enabled",
          "chat.languageRestrictions.ukrainian.enabled",
          "chat.languageRestrictions.otherNonEnglish.enabled",
        ],
        disclaimerPage: [
          "disclaimer.title",
          "disclaimer.bodyMarkdown",
        ],
        homePage: [
          "home.profileCard.name",
          "home.profileCard.summary",
          "home.featuredProject.title",
          "home.featuredProject.description",
        ],
        resumePdf: [
          "resume.pageHeading",
          "resume.downloadFileNameBase",
          "resume.pdf.displayName",
          "resume.pdf.headerLinkVisibility.website",
        ],
        siteIdentity: [
          "site.name",
          "site.canonicalUrl",
          "owner.displayName",
          "owner.roleTitle",
          "seo.defaultTitle",
          "seo.description",
        ],
      };
      const preferredPaths = preferredPathsBySection[sectionId] ?? [];
      const preferredFields = preferredPaths
        .map((path) => fields.find((field) => field.path === path))
        .filter(Boolean);

      if (preferredFields.length > 0) {
        return preferredFields;
      }

      return fields.slice(0, 6);
    }

    function appendPreviewItem(label, value) {
      const item = document.createElement("div");
      item.className = "preview-item";

      const itemLabel = document.createElement("div");
      itemLabel.className = "preview-label";
      itemLabel.textContent = label;

      const itemValue = document.createElement("div");
      itemValue.className = "preview-value";
      itemValue.textContent = value;

      item.append(itemLabel, itemValue);
      elements.previewList.appendChild(item);
    }

    function formatDisplayValue(field, rawValue) {
      if (!field) {
        return rawValue;
      }

      if (/^chat\.quickPrompts\[\d+\]\.responses$/.test(field.path)) {
        try {
          const responses = JSON.parse(rawValue);
          if (Array.isArray(responses)) {
            return responses
              .map((response, index) => \`Response \${index + 1}:\\n\${String(response)}\`)
              .join("\\n\\n");
          }
        } catch {
          return rawValue;
        }
      }

      if (field.type === "boolean") {
        return getBooleanDisplayLabel(field.path, rawValue === "true");
      }

      return rawValue;
    }

    function getBooleanDisplayLabel(path, checked) {
      if (path.includes(".linkVisibility.") || path.includes(".headerLinkVisibility.")) {
        return checked ? "Included" : "Hidden";
      }
      if (path.startsWith("chat.languageRestrictions.")) {
        return checked ? "Restricted" : "Allowed";
      }
      return checked ? "Enabled" : "Disabled";
    }

    function showReview() {
      clearValidation();
      const assignments = getAssignments();
      state.activeSectionId = REVIEW_SECTION_ID;
      elements.sectionTitle.textContent = "Review & Save";
      elements.sectionDescription.textContent = "Validate the current diff before writing project config.";
      elements.fields.classList.add("hidden");
      elements.reviewPanel.classList.add("visible");
      elements.reviewList.textContent = "";
      renderPreview(null, []);
      updateSummary();

      if (assignments.length === 0) {
        setNotice("warning", "No changes to review.");
        elements.saveButton.disabled = true;
        renderTabs();
        return;
      }

      setNotice("warning", "Review all changes, then validate them before saving.");

      for (const assignment of assignments) {
        const field = getField(assignment.path);
        const item = document.createElement("article");
        item.className = "review-item";

        const path = document.createElement("div");
        path.className = "review-path";
        path.textContent = field
          ? field.label + " (" + assignment.path + ")"
          : assignment.path;

        const grid = document.createElement("div");
        grid.className = "diff-grid";

        const oldValue = document.createElement("div");
        oldValue.className = "diff-box";
        oldValue.textContent = field
          ? formatDisplayValue(field, serialiseValue(field))
          : "";

        const newValue = document.createElement("div");
        newValue.className = "diff-box";
        newValue.textContent = formatDisplayValue(field, assignment.rawValue);

        grid.append(oldValue, newValue);
        item.append(path, grid);
        elements.reviewList.appendChild(item);
      }

      renderTabs();
    }

    async function validateChanges() {
      const assignments = getAssignments();
      if (assignments.length === 0) {
        setNotice("warning", "No changes to validate.");
        return;
      }

      elements.validateButton.disabled = true;
      setNotice("warning", "Validating current changes...");

      try {
        const result = await apiPost("/api/preview", { assignments });
        elements.validationOutput.classList.add("visible");
        elements.validationOutput.textContent = result.validation.output || "Validation completed.";

        if (result.validation.passed) {
          state.validationKey = result.validationKey;
          state.validatedAssignmentsKey = assignmentKey(assignments);
          elements.saveButton.disabled = false;
          setNotice("success", "Validation passed. You can save these exact changes.");
          renderPreviewChanges(result.changes);
          renderFollowUps(result.followUpActions);
        } else {
          clearValidation(false);
          setNotice("danger", "Validation failed. Fix the listed issues before saving.");
          renderPreviewChanges(result.changes);
        }
      } catch (error) {
        clearValidation(false);
        setNotice("danger", error.message);
      } finally {
        elements.validateButton.disabled = false;
      }
    }

    function renderPreviewChanges(changes) {
      elements.reviewList.textContent = "";

      if (changes.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No changed values.";
        elements.reviewList.appendChild(empty);
        return;
      }

      for (const change of changes) {
        const item = document.createElement("article");
        item.className = "review-item";

        const path = document.createElement("div");
        path.className = "review-path";
        const field = getField(change.path);
        path.textContent = field ? field.label + " (" + change.path + ")" : change.path;

        const grid = document.createElement("div");
        grid.className = "diff-grid";

        const oldValue = document.createElement("div");
        oldValue.className = "diff-box";
        oldValue.textContent = JSON.stringify(change.oldValue, null, 2);

        const newValue = document.createElement("div");
        newValue.className = "diff-box";
        newValue.textContent = JSON.stringify(change.newValue, null, 2);

        grid.append(oldValue, newValue);
        item.append(path, grid);
        elements.reviewList.appendChild(item);
      }
    }

    async function saveChanges() {
      const assignments = getAssignments();
      if (!state.validationKey || state.validatedAssignmentsKey !== assignmentKey(assignments)) {
        setNotice("danger", "Review and validate the current changes before saving.");
        elements.saveButton.disabled = true;
        return;
      }

      elements.saveButton.disabled = true;
      setNotice("warning", "Saving validated changes...");

      try {
        const result = await apiPost("/api/save", {
          assignments,
          validationKey: state.validationKey,
        });

        elements.validationOutput.classList.add("visible");
        elements.validationOutput.textContent =
          result.validation?.output || result.error || "Save completed.";

        if (!result.ok) {
          setNotice("danger", result.error || "Save failed.");
          return;
        }

        setNotice("success", result.saved ? "Config saved and validated." : "No changes were saved.");
        await loadState();
        elements.reviewPanel.classList.add("visible");
        setNotice("success", "Config saved and validated.");
      } catch (error) {
        setNotice("danger", error.message);
      }
    }

    function renderFollowUps(actions = state.followUpActions) {
      elements.followUpList.textContent = "";
      for (const action of actions) {
        const item = document.createElement("div");
        item.className = "review-item";
        item.textContent = action;
        elements.followUpList.appendChild(item);
      }
    }

    function getAssignments() {
      return state.fields
        .filter((field) => isChanged(field))
        .map((field) => ({
          path: field.path,
          rawValue: state.values.get(field.path) ?? serialiseValue(field),
        }))
        .sort((left, right) => left.path.localeCompare(right.path));
    }

    function getField(path) {
      return state.fields.find((field) => field.path === path);
    }

    function isChanged(field) {
      return (state.values.get(field.path) ?? serialiseValue(field)) !== serialiseValue(field);
    }

    function serialiseValue(field) {
      if (field.type === "array") {
        return JSON.stringify(field.value, null, 2);
      }
      if (field.type === "number" || field.type === "boolean") {
        return String(field.value);
      }
      if (field.value === null) {
        return "null";
      }
      return String(field.value);
    }

    function assignmentKey(assignments) {
      return JSON.stringify(assignments);
    }

    function clearValidation(hideOutput = true) {
      state.validationKey = null;
      state.validatedAssignmentsKey = "";
      elements.saveButton.disabled = true;
      if (hideOutput) {
        elements.validationOutput.classList.remove("visible");
        elements.validationOutput.textContent = "";
      }
    }

    function setNotice(kind, message) {
      elements.reviewNotice.className = \`notice visible \${kind}\`;
      elements.reviewNotice.textContent = message;
    }

    function showTopError(message) {
      elements.sectionTitle.textContent = "Could not load wizard";
      elements.sectionDescription.textContent = message;
    }

    async function apiGet(path) {
      const response = await fetch(path, {
        headers: { "X-Wizard-Token": token },
      });
      return parseResponse(response);
    }

    async function apiPost(path, body) {
      const response = await fetch(path, {
        body: JSON.stringify(body),
        headers: {
          "Content-Type": "application/json",
          "X-Wizard-Token": token,
        },
        method: "POST",
      });
      return parseResponse(response);
    }

    async function parseResponse(response) {
      const body = await response.json();
      if (!response.ok || body.ok === false) {
        throw new Error(body.error || \`Request failed with status \${response.status}\`);
      }
      return body;
    }

    function cssEscape(value) {
      if (window.CSS && typeof window.CSS.escape === "function") {
        return window.CSS.escape(value);
      }
      return value.replace(/["\\\\]/g, "\\\\$&");
    }
  </script>
</body>
</html>`;
}
