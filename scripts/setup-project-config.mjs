#!/usr/bin/env node

import { stdin as input, stdout as output } from "node:process";
import { createInterface } from "node:readline/promises";

import {
  applyAssignmentsToRaw,
  formatChangeSummary,
  formatValueForDisplay,
  getFollowUpActions,
  listEditableFields,
  listEditableSections,
  loadProjectConfig,
  parseAssignment,
  runProjectConfigValidation,
  writeProjectConfig,
} from "./lib/project-config-wizard.mjs";

main().catch((error) => {
  console.error(`Setup wizard failed: ${error.message}`);
  process.exit(1);
});

async function main() {
  const options = parseCliOptions(process.argv.slice(2));
  const projectConfig = loadProjectConfig(options.configPath);

  if (options.help) {
    printHelp();
    return;
  }

  if (options.listSections) {
    printSections(projectConfig.config);
    return;
  }

  if (options.listFields) {
    printFields(projectConfig.config, options.sectionId);
    return;
  }

  const assignments =
    options.assignments.length > 0
      ? options.assignments
      : await promptForAssignments(projectConfig.config, options.sectionId);

  const result = applyAssignmentsToRaw(
    projectConfig.raw,
    projectConfig.config,
    assignments,
  );

  console.log("");
  console.log("Planned changes:");
  console.log(formatChangeSummary(result.changes));

  if (result.changes.length === 0) {
    console.log("");
    console.log("Project config was not changed.");
    return;
  }

  if (options.dryRun) {
    console.log("");
    console.log("Dry run only. Project config was not written.");
    printFollowUps(result.config);
    return;
  }

  writeProjectConfig(projectConfig.path, result.patchedRaw);

  const validation = runProjectConfigValidation(projectConfig.path);
  if (validation.stdout) {
    process.stdout.write(validation.stdout);
  }
  if (validation.stderr) {
    process.stderr.write(validation.stderr);
  }

  if (validation.status !== 0 || validation.error) {
    writeProjectConfig(projectConfig.path, projectConfig.raw);
    const detail = validation.error ? ` ${validation.error.message}` : "";
    throw new Error(
      `Validation failed after writing config; original file was restored.${detail}`,
    );
  }

  console.log("");
  console.log(`Updated ${projectConfig.path}.`);
  printFollowUps(result.config);
}

function parseCliOptions(args) {
  const options = {
    assignments: [],
    configPath: undefined,
    dryRun: false,
    help: false,
    listFields: false,
    listSections: false,
    sectionId: "all",
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];

    if (arg === "--help" || arg === "-h") {
      options.help = true;
      continue;
    }

    if (arg === "--config") {
      options.configPath = readOptionValue(args, index, arg);
      index += 1;
      continue;
    }

    if (arg === "--section") {
      options.sectionId = readOptionValue(args, index, arg);
      index += 1;
      continue;
    }

    if (arg === "--set") {
      options.assignments.push(parseAssignment(readOptionValue(args, index, arg)));
      index += 1;
      continue;
    }

    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }

    if (arg === "--list-sections") {
      options.listSections = true;
      continue;
    }

    if (arg === "--list-fields") {
      options.listFields = true;
      continue;
    }

    throw new Error(`Unknown option: ${arg}`);
  }

  return options;
}

async function promptForAssignments(config, sectionId) {
  const sections = listEditableSections(config);
  let selectedSectionId = sectionId;

  const readline = createInterface({ input, output });

  try {
    if (selectedSectionId === "all") {
      printSections(config);
      const answer = await readline.question(
        "\nSection id to edit, or all for every section: ",
      );
      selectedSectionId = answer.trim() || "all";
    }

    const fields = listEditableFields(config, selectedSectionId);
    const assignments = [];

    console.log("");
    console.log(`Editing ${fields.length} field(s). Press Enter to keep a value.`);
    console.log("Arrays and objects must be entered as JSON.");

    for (const field of fields) {
      console.log("");
      console.log(`${field.path}`);
      console.log(`Current: ${formatValueForDisplay(field.value, 900)}`);

      const answer = await readline.question("New value: ");
      if (answer.length === 0) {
        continue;
      }

      assignments.push({
        path: field.path,
        rawValue: answer,
      });
    }

    if (assignments.length === 0) {
      return assignments;
    }

    const confirmation = await readline.question(
      "\nWrite these changes after validation? Type yes to continue: ",
    );
    if (confirmation.trim().toLowerCase() !== "yes") {
      console.log("Cancelled.");
      return [];
    }

    return assignments;
  } finally {
    readline.close();
  }
}

function printSections(config) {
  console.log("Editable project config sections:");

  for (const section of listEditableSections(config)) {
    console.log(`- ${section.id}: ${section.title}`);
    console.log(`  paths: ${section.paths.join(", ")}`);
  }
}

function printFields(config, sectionId) {
  const fields = listEditableFields(config, sectionId);

  console.log(`Editable fields for section ${sectionId}:`);
  for (const field of fields) {
    console.log(`- ${field.path}: ${formatValueForDisplay(field.value, 240)}`);
  }
}

function printFollowUps(config) {
  console.log("");
  console.log("Follow-up actions:");

  for (const action of getFollowUpActions(config)) {
    console.log(`- ${action}`);
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
  node scripts/setup-project-config.mjs [options]

Options:
  --config <path>       Use a project config file. Defaults to config/project.config.json.
  --list-sections       Print editable sections from wizard.editableSections.
  --list-fields         Print editable fields. Combine with --section <id>.
  --section <id>        Edit or list one section. Defaults to all.
  --set <path=value>    Set a value without interactive prompts. Can be repeated.
  --dry-run             Show changes without writing the config.
  --help                Show this help.

Examples:
  node scripts/setup-project-config.mjs --list-sections
  node scripts/setup-project-config.mjs --section chatSettings
  node scripts/setup-project-config.mjs --set owner.shortName=Jordan --dry-run
  node scripts/setup-project-config.mjs --set 'seo.keywords=["Python","FastAPI"]'
`);
}
