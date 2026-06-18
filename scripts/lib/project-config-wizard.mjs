import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const moduleDir = dirname(fileURLToPath(import.meta.url));

export const REPO_ROOT = resolve(moduleDir, "..", "..");
export const DEFAULT_CONFIG_PATH = resolve(
  REPO_ROOT,
  "config",
  "project.config.json",
);
export const PROJECT_CONFIG_CHECK_SCRIPT = resolve(
  REPO_ROOT,
  "scripts",
  "check-project-config.mjs",
);

export function resolveProjectPath(pathValue) {
  if (!pathValue) {
    return DEFAULT_CONFIG_PATH;
  }

  return isAbsolute(pathValue) ? pathValue : resolve(REPO_ROOT, pathValue);
}

export function loadProjectConfig(configPath = DEFAULT_CONFIG_PATH) {
  const resolvedPath = resolveProjectPath(configPath);
  const raw = readFileSync(resolvedPath, "utf8");

  return {
    config: JSON.parse(raw),
    path: resolvedPath,
    raw,
  };
}

export function writeProjectConfig(configPath, rawConfig) {
  writeFileSync(resolveProjectPath(configPath), rawConfig, "utf8");
}

export function listEditableSections(config) {
  const sections = getValueAtPath(config, "wizard.editableSections");

  if (!Array.isArray(sections)) {
    throw new Error("wizard.editableSections must be an array.");
  }

  return sections.map((section) => {
    if (!isPlainObject(section)) {
      throw new Error("Each wizard section must be an object.");
    }
    if (typeof section.id !== "string" || section.id.trim().length === 0) {
      throw new Error("Each wizard section must have a non-empty id.");
    }
    if (typeof section.title !== "string" || section.title.trim().length === 0) {
      throw new Error(`Wizard section ${section.id} must have a non-empty title.`);
    }
    if (!Array.isArray(section.paths) || section.paths.length === 0) {
      throw new Error(`Wizard section ${section.id} must have editable paths.`);
    }

    return {
      id: section.id,
      paths: [...section.paths],
      title: section.title,
    };
  });
}

export function listEditableFields(config, sectionId = "all") {
  const sections = listEditableSections(config);
  const selectedSections =
    sectionId === "all"
      ? sections
      : sections.filter((section) => section.id === sectionId);

  if (selectedSections.length === 0) {
    const available = sections.map((section) => section.id).join(", ");
    throw new Error(`Unknown section "${sectionId}". Available sections: ${available}.`);
  }

  const seenPaths = new Set();
  const fields = [];

  for (const section of selectedSections) {
    for (const editablePath of section.paths) {
      const value = getValueAtPath(config, editablePath);

      if (value === undefined) {
        throw new Error(`Editable path does not exist: ${editablePath}.`);
      }

      for (const field of collectEditableFields(value, editablePath)) {
        if (seenPaths.has(field.path)) {
          continue;
        }

        seenPaths.add(field.path);
        fields.push({
          ...field,
          sectionId: section.id,
          sectionTitle: section.title,
        });
      }
    }
  }

  return fields;
}

export function parsePath(pathValue) {
  if (typeof pathValue !== "string" || pathValue.trim().length === 0) {
    throw new Error("Path must be a non-empty string.");
  }

  const segments = [];
  let token = "";
  let index = 0;

  while (index < pathValue.length) {
    const character = pathValue[index];

    if (character === ".") {
      pushPathToken(segments, token, pathValue);
      token = "";
      index += 1;
      continue;
    }

    if (character === "[") {
      if (token.length > 0) {
        pushPathToken(segments, token, pathValue);
        token = "";
      }

      const endIndex = pathValue.indexOf("]", index + 1);
      if (endIndex === -1) {
        throw new Error(`Invalid path segment in ${pathValue}.`);
      }

      const rawIndex = pathValue.slice(index + 1, endIndex);
      if (!/^\d+$/.test(rawIndex)) {
        throw new Error(`Invalid array index in ${pathValue}.`);
      }

      segments.push(Number(rawIndex));
      index = endIndex + 1;
      continue;
    }

    token += character;
    index += 1;
  }

  pushPathToken(segments, token, pathValue);
  return segments;
}

export function formatPath(segments) {
  return segments
    .map((segment, index) => {
      if (typeof segment === "number") {
        return `[${segment}]`;
      }

      return index === 0 ? segment : `.${segment}`;
    })
    .join("");
}

export function getValueAtPath(source, pathValue) {
  const segments = Array.isArray(pathValue) ? pathValue : parsePath(pathValue);
  let current = source;

  for (const segment of segments) {
    if (Array.isArray(current)) {
      if (typeof segment !== "number" || segment < 0 || segment >= current.length) {
        return undefined;
      }
      current = current[segment];
      continue;
    }

    if (!isPlainObject(current) || typeof segment !== "string") {
      return undefined;
    }

    if (!Object.hasOwn(current, segment)) {
      return undefined;
    }

    current = current[segment];
  }

  return current;
}

export function setValueAtPath(source, pathValue, nextValue) {
  const segments = Array.isArray(pathValue) ? pathValue : parsePath(pathValue);

  if (segments.length === 0) {
    throw new Error("Cannot set an empty path.");
  }

  let current = source;

  for (const segment of segments.slice(0, -1)) {
    current = getChildForSet(current, segment, pathValue);
  }

  const lastSegment = segments.at(-1);

  if (Array.isArray(current)) {
    if (
      typeof lastSegment !== "number" ||
      lastSegment < 0 ||
      lastSegment >= current.length
    ) {
      throw new Error(`Path does not exist: ${formatPath(segments)}.`);
    }

    current[lastSegment] = nextValue;
    return;
  }

  if (
    !isPlainObject(current) ||
    typeof lastSegment !== "string" ||
    !Object.hasOwn(current, lastSegment)
  ) {
    throw new Error(`Path does not exist: ${formatPath(segments)}.`);
  }

  current[lastSegment] = nextValue;
}

export function parseAssignment(rawAssignment) {
  const separatorIndex = rawAssignment.indexOf("=");

  if (separatorIndex <= 0) {
    throw new Error(`Assignment must use path=value format: ${rawAssignment}`);
  }

  return {
    path: rawAssignment.slice(0, separatorIndex).trim(),
    rawValue: rawAssignment.slice(separatorIndex + 1),
  };
}

export function parseAssignmentValue(rawValue, currentValue, pathValue = "value") {
  if (Array.isArray(currentValue)) {
    const parsedValue = parseJsonReplacement(rawValue, pathValue);

    if (!Array.isArray(parsedValue)) {
      throw new Error(`${pathValue} currently stores an array, so the new value must be JSON array syntax.`);
    }

    return parsedValue;
  }

  if (isPlainObject(currentValue)) {
    const parsedValue = parseJsonReplacement(rawValue, pathValue);

    if (!isPlainObject(parsedValue)) {
      throw new Error(`${pathValue} currently stores an object, so the new value must be JSON object syntax.`);
    }

    return parsedValue;
  }

  if (typeof currentValue === "number") {
    const parsedNumber = Number(rawValue);

    if (!Number.isFinite(parsedNumber)) {
      throw new Error(`${pathValue} must be a finite number.`);
    }

    return parsedNumber;
  }

  if (typeof currentValue === "boolean") {
    if (rawValue === "true") {
      return true;
    }
    if (rawValue === "false") {
      return false;
    }

    throw new Error(`${pathValue} must be true or false.`);
  }

  if (currentValue === null) {
    return parseJsonReplacement(rawValue, pathValue);
  }

  return rawValue;
}

export function applyAssignmentsToRaw(rawConfig, config, assignments) {
  const workingConfig = cloneJson(config);
  const changes = [];

  for (const assignment of assignments) {
    const segments = parsePath(assignment.path);
    const pathValue = formatPath(segments);
    const currentValue = getValueAtPath(workingConfig, segments);

    if (currentValue === undefined) {
      throw new Error(`Path does not exist: ${pathValue}.`);
    }

    const nextValue = parseAssignmentValue(
      assignment.rawValue,
      currentValue,
      pathValue,
    );

    if (jsonEquals(currentValue, nextValue)) {
      continue;
    }

    setValueAtPath(workingConfig, segments, nextValue);
    changes.push({
      newValue: nextValue,
      oldValue: currentValue,
      path: pathValue,
      segments,
    });
  }

  assertNoOverlappingChanges(changes);

  if (changes.length === 0) {
    return {
      changes,
      config: workingConfig,
      patchedRaw: rawConfig,
    };
  }

  const replacements = changes
    .map((change) => {
      const span = findJsonValueSpan(rawConfig, change.segments);
      const baseIndent = getLineIndent(rawConfig, span.start);

      return {
        ...span,
        replacement: stringifyJsonValue(change.newValue, baseIndent),
      };
    })
    .sort((left, right) => right.start - left.start);

  let patchedRaw = rawConfig;

  for (const replacement of replacements) {
    patchedRaw =
      patchedRaw.slice(0, replacement.start) +
      replacement.replacement +
      patchedRaw.slice(replacement.end);
  }

  return {
    changes,
    config: workingConfig,
    patchedRaw,
  };
}

export function stringifyJsonValue(value, baseIndent = "") {
  const formatted = escapeNonAscii(JSON.stringify(value, null, 2));
  const lines = formatted.split("\n");

  if (lines.length === 1) {
    return formatted;
  }

  return [
    lines[0],
    ...lines.slice(1).map((line) => `${baseIndent}${line}`),
  ].join("\n");
}

export function escapeNonAscii(value) {
  return value.replace(/[^\x00-\x7F]/gu, (character) => {
    const codePoint = character.codePointAt(0);

    if (codePoint <= 0xffff) {
      return toUnicodeEscape(codePoint);
    }

    const adjusted = codePoint - 0x10000;
    const highSurrogate = 0xd800 + (adjusted >> 10);
    const lowSurrogate = 0xdc00 + (adjusted & 0x3ff);

    return `${toUnicodeEscape(highSurrogate)}${toUnicodeEscape(lowSurrogate)}`;
  });
}

export function formatValueForDisplay(value, maxLength = 500) {
  const formatted =
    typeof value === "string" ? JSON.stringify(value) : JSON.stringify(value);

  if (formatted.length <= maxLength) {
    return formatted;
  }

  return `${formatted.slice(0, maxLength - 3)}...`;
}

export function formatChangeSummary(changes) {
  if (changes.length === 0) {
    return "No changes.";
  }

  return changes
    .map(
      (change) =>
        `${change.path}: ${formatValueForDisplay(change.oldValue, 160)} -> ${formatValueForDisplay(change.newValue, 160)}`,
    )
    .join("\n");
}

export function getFollowUpActions(config) {
  const resumePath =
    getValueAtPath(config, "content.publicResumePath") ??
    "the configured public resume path";

  return [
    "Run `task config:check` after editing project config.",
    "Run `task ci` before push or pull request.",
    `Review \`${resumePath}\` separately when replacing public resume or RAG content.`,
    `Run \`task rag:ingest\` only after changing \`${resumePath}\` and approving public RAG content.`,
    "Set `BACKEND_ORIGIN` in Vercel and backend secrets in the hosting provider dashboard, not in project config.",
  ];
}

export function runProjectConfigValidation(configPath = DEFAULT_CONFIG_PATH) {
  return spawnSync(
    process.execPath,
    [PROJECT_CONFIG_CHECK_SCRIPT, "--config", resolveProjectPath(configPath)],
    {
      cwd: REPO_ROOT,
      encoding: "utf8",
      env: process.env,
    },
  );
}

export function findJsonValueSpan(rawConfig, pathValue) {
  const segments = Array.isArray(pathValue) ? pathValue : parsePath(pathValue);
  let span = {
    end: skipValue(rawConfig, skipWhitespace(rawConfig, 0)),
    start: skipWhitespace(rawConfig, 0),
  };

  for (const segment of segments) {
    const valueStart = skipWhitespace(rawConfig, span.start);
    const character = rawConfig[valueStart];

    if (typeof segment === "number") {
      if (character !== "[") {
        throw new Error(`Expected array while resolving ${formatPath(segments)}.`);
      }

      span = findArrayItemSpan(rawConfig, valueStart, segment);
      continue;
    }

    if (character !== "{") {
      throw new Error(`Expected object while resolving ${formatPath(segments)}.`);
    }

    span = findObjectPropertySpan(rawConfig, valueStart, segment);
  }

  return span;
}

function collectEditableFields(value, basePath) {
  if (Array.isArray(value)) {
    if (value.length === 0 || value.every((item) => !isPlainObject(item))) {
      return [{ path: basePath, value }];
    }

    return value.flatMap((item, index) => {
      const itemPath = `${basePath}[${index}]`;

      if (isPlainObject(item)) {
        return collectEditableFields(item, itemPath);
      }

      return [{ path: itemPath, value: item }];
    });
  }

  if (isPlainObject(value)) {
    const fields = Object.entries(value).flatMap(([key, childValue]) =>
      collectEditableFields(childValue, `${basePath}.${key}`),
    );

    return fields.length > 0 ? fields : [{ path: basePath, value }];
  }

  return [{ path: basePath, value }];
}

function pushPathToken(segments, token, originalPath) {
  if (token.length === 0) {
    if (segments.length === 0) {
      throw new Error(`Invalid path: ${originalPath}.`);
    }
    return;
  }

  segments.push(token);
}

function getChildForSet(current, segment, originalPath) {
  if (Array.isArray(current)) {
    if (typeof segment !== "number" || segment < 0 || segment >= current.length) {
      throw new Error(`Path does not exist: ${originalPath}.`);
    }

    return current[segment];
  }

  if (!isPlainObject(current) || typeof segment !== "string") {
    throw new Error(`Path does not exist: ${originalPath}.`);
  }

  if (!Object.hasOwn(current, segment)) {
    throw new Error(`Path does not exist: ${originalPath}.`);
  }

  return current[segment];
}

function parseJsonReplacement(rawValue, pathValue) {
  try {
    return JSON.parse(rawValue);
  } catch (error) {
    throw new Error(`${pathValue} must be valid JSON: ${error.message}`);
  }
}

function assertNoOverlappingChanges(changes) {
  for (let leftIndex = 0; leftIndex < changes.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < changes.length; rightIndex += 1) {
      const left = changes[leftIndex];
      const right = changes[rightIndex];

      if (isPathPrefix(left.segments, right.segments) || isPathPrefix(right.segments, left.segments)) {
        throw new Error(
          `Assignments must not overlap: ${left.path} and ${right.path}.`,
        );
      }
    }
  }
}

function isPathPrefix(leftSegments, rightSegments) {
  if (leftSegments.length > rightSegments.length) {
    return false;
  }

  return leftSegments.every((segment, index) => segment === rightSegments[index]);
}

function findObjectPropertySpan(rawConfig, objectStart, key) {
  let index = skipWhitespace(rawConfig, objectStart + 1);

  if (rawConfig[index] === "}") {
    throw new Error(`Object property does not exist: ${key}.`);
  }

  while (index < rawConfig.length) {
    const property = readJsonString(rawConfig, index);
    index = skipWhitespace(rawConfig, property.end);

    expectCharacter(rawConfig, index, ":");
    const valueStart = skipWhitespace(rawConfig, index + 1);
    const valueEnd = skipValue(rawConfig, valueStart);

    if (property.value === key) {
      return {
        end: valueEnd,
        start: valueStart,
      };
    }

    index = skipWhitespace(rawConfig, valueEnd);

    if (rawConfig[index] === ",") {
      index = skipWhitespace(rawConfig, index + 1);
      continue;
    }

    if (rawConfig[index] === "}") {
      break;
    }

    throw new Error(`Invalid JSON object near index ${index}.`);
  }

  throw new Error(`Object property does not exist: ${key}.`);
}

function findArrayItemSpan(rawConfig, arrayStart, itemIndex) {
  let index = skipWhitespace(rawConfig, arrayStart + 1);
  let currentIndex = 0;

  if (rawConfig[index] === "]") {
    throw new Error(`Array item does not exist: ${itemIndex}.`);
  }

  while (index < rawConfig.length) {
    const valueStart = index;
    const valueEnd = skipValue(rawConfig, valueStart);

    if (currentIndex === itemIndex) {
      return {
        end: valueEnd,
        start: valueStart,
      };
    }

    currentIndex += 1;
    index = skipWhitespace(rawConfig, valueEnd);

    if (rawConfig[index] === ",") {
      index = skipWhitespace(rawConfig, index + 1);
      continue;
    }

    if (rawConfig[index] === "]") {
      break;
    }

    throw new Error(`Invalid JSON array near index ${index}.`);
  }

  throw new Error(`Array item does not exist: ${itemIndex}.`);
}

function skipValue(rawConfig, index) {
  const valueStart = skipWhitespace(rawConfig, index);
  const character = rawConfig[valueStart];

  if (character === "{") {
    return skipObject(rawConfig, valueStart);
  }

  if (character === "[") {
    return skipArray(rawConfig, valueStart);
  }

  if (character === "\"") {
    return readJsonString(rawConfig, valueStart).end;
  }

  if (character === "-" || /\d/.test(character)) {
    return skipNumber(rawConfig, valueStart);
  }

  if (rawConfig.startsWith("true", valueStart)) {
    return valueStart + 4;
  }

  if (rawConfig.startsWith("false", valueStart)) {
    return valueStart + 5;
  }

  if (rawConfig.startsWith("null", valueStart)) {
    return valueStart + 4;
  }

  throw new Error(`Invalid JSON value near index ${valueStart}.`);
}

function skipObject(rawConfig, objectStart) {
  let index = skipWhitespace(rawConfig, objectStart + 1);

  if (rawConfig[index] === "}") {
    return index + 1;
  }

  while (index < rawConfig.length) {
    const property = readJsonString(rawConfig, index);
    index = skipWhitespace(rawConfig, property.end);
    expectCharacter(rawConfig, index, ":");
    index = skipWhitespace(rawConfig, skipValue(rawConfig, index + 1));

    if (rawConfig[index] === ",") {
      index = skipWhitespace(rawConfig, index + 1);
      continue;
    }

    if (rawConfig[index] === "}") {
      return index + 1;
    }

    throw new Error(`Invalid JSON object near index ${index}.`);
  }

  throw new Error("Unexpected end of JSON object.");
}

function skipArray(rawConfig, arrayStart) {
  let index = skipWhitespace(rawConfig, arrayStart + 1);

  if (rawConfig[index] === "]") {
    return index + 1;
  }

  while (index < rawConfig.length) {
    index = skipWhitespace(rawConfig, skipValue(rawConfig, index));

    if (rawConfig[index] === ",") {
      index = skipWhitespace(rawConfig, index + 1);
      continue;
    }

    if (rawConfig[index] === "]") {
      return index + 1;
    }

    throw new Error(`Invalid JSON array near index ${index}.`);
  }

  throw new Error("Unexpected end of JSON array.");
}

function readJsonString(rawConfig, stringStart) {
  expectCharacter(rawConfig, stringStart, "\"");

  let index = stringStart + 1;

  while (index < rawConfig.length) {
    const character = rawConfig[index];

    if (character === "\\") {
      index += 2;
      continue;
    }

    if (character === "\"") {
      const end = index + 1;
      return {
        end,
        value: JSON.parse(rawConfig.slice(stringStart, end)),
      };
    }

    index += 1;
  }

  throw new Error("Unexpected end of JSON string.");
}

function skipNumber(rawConfig, numberStart) {
  const match = rawConfig
    .slice(numberStart)
    .match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);

  if (!match) {
    throw new Error(`Invalid JSON number near index ${numberStart}.`);
  }

  return numberStart + match[0].length;
}

function skipWhitespace(rawConfig, index) {
  let currentIndex = index;

  while (/\s/.test(rawConfig[currentIndex] ?? "")) {
    currentIndex += 1;
  }

  return currentIndex;
}

function expectCharacter(rawConfig, index, expected) {
  if (rawConfig[index] !== expected) {
    throw new Error(`Expected "${expected}" near index ${index}.`);
  }
}

function getLineIndent(rawConfig, index) {
  const lineStart = rawConfig.lastIndexOf("\n", index - 1) + 1;
  const line = rawConfig.slice(lineStart, index);
  const match = line.match(/^\s*/);

  return match ? match[0] : "";
}

function toUnicodeEscape(codePoint) {
  return `\\u${codePoint.toString(16).padStart(4, "0")}`;
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function jsonEquals(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
