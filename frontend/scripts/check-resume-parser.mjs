import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REPOSITORY_ROOT = resolve(SCRIPT_DIR, "..", "..");
const RESUME_PATHS = [
  join(REPOSITORY_ROOT, "content", "resume.md"),
  join(REPOSITORY_ROOT, "frontend", "content", "resume.md"),
];

const SUMMARY_RAG_MARKER = "## RAG";
const ENTRY_RAG_MARKER = "### RAG";
const RAG_ONLY_SENTINEL = "RAG_ONLY_SENTINEL";

const resumePath = RESUME_PATHS.find((path) => existsSync(path));

if (!resumePath) {
  throw new Error("Static resume markdown source was not found.");
}

const markdown = normalizeLineEndings(readFileSync(resumePath, "utf8"));
const currentData = parseResume(markdown, { ignoreRagSections: true });
const legacyData = parseResume(stripRagSections(markdown), {
  ignoreRagSections: false,
});

assert.deepEqual(currentData, legacyData);
runNoLeakFixtureTest();

const tmpDir = join(REPOSITORY_ROOT, ".tmp");
mkdirSync(tmpDir, { recursive: true });

const conciseSnapshot = renderResumeSnapshot(currentData, "concise");
const detailedSnapshot = renderResumeSnapshot(currentData, "detailed");

assertNoRagLeak(conciseSnapshot);
assertNoRagLeak(detailedSnapshot);

const concisePath = join(tmpDir, "resume-concise.generated.txt");
const detailedPath = join(tmpDir, "resume-detailed.generated.txt");

writeFileSync(concisePath, conciseSnapshot, "utf8");
writeFileSync(detailedPath, detailedSnapshot, "utf8");

console.log("Resume parser check passed.");
console.log(`Generated: ${concisePath}`);
console.log(`Generated: ${detailedPath}`);

function parseResume(source, options) {
  const summary = parseSummary(source, options);
  const entries = parseEntries(source, options);
  const additionalSections = parseAdditionalSections(source);

  return {
    summary,
    entries: entries.sort(compareResumeEntries),
    additionalSections,
  };
}

function parseSummary(source, options) {
  const summaryMarkdown = extractRequiredSection(source, "# Summary", "# Entries");
  const concise = extractRequiredSection(
    summaryMarkdown,
    "## Concise",
    "## Detailed",
  );
  const detailed = options.ignoreRagSections
    ? extractRequiredSection(
        summaryMarkdown,
        "## Detailed",
        SUMMARY_RAG_MARKER,
        { requireEndMarker: false },
      )
    : extractRequiredSection(summaryMarkdown, "## Detailed");

  return {
    concise: parseParagraphs(concise),
    detailed: parseParagraphs(detailed),
  };
}

function parseEntries(source, options) {
  const entriesMarkdown = extractRequiredSection(
    source,
    "# Entries",
    "# Additional Sections",
  );

  return splitEntryBlocks(entriesMarkdown).map((block) => {
    const metadataBlock = block.match(/```yaml\n([\s\S]*?)\n```/)?.[1];

      if (!metadataBlock) {
        throw new Error("Resume entry metadata block is missing.");
      }

      const conciseMarkdown = extractRequiredSection(
        block,
        "### Concise",
        "### Detailed",
      );
      const detailedMarkdown = options.ignoreRagSections
        ? extractRequiredSection(
            block,
            "### Detailed",
            ENTRY_RAG_MARKER,
            { requireEndMarker: false },
          )
        : extractRequiredSection(block, "### Detailed");
      const { website, ...metadata } = parseMetadata(metadataBlock);

      if (!website) {
        return null;
      }

      return {
        ...metadata,
        concise: parseBullets(conciseMarkdown),
        detailed: parseBullets(detailedMarkdown),
      };
    })
    .filter((entry) => entry !== null);
}

function splitEntryBlocks(source) {
  return source
    .trim()
    .split(/\n(?=## )/)
    .map((block) => block.trim())
    .filter((block) => block.startsWith("## "));
}

function parseAdditionalSections(source) {
  const additionalMarkdown = extractOptionalSection(
    source,
    "# Additional Sections",
  );

  if (!additionalMarkdown) {
    return [];
  }

  const pattern = /(?:^|\n\n)## ([^\n]+)\n\n([\s\S]*?)(?=\n\n## |\s*$)/g;

  return Array.from(additionalMarkdown.matchAll(pattern)).map((match) => {
    const title = match[1].trim();

    return {
      id: title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
      title,
      items: parseAdditionalItems(match[2]),
    };
  });
}

function parseAdditionalItems(markdown) {
  return markdown
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim())
    .map(parseAdditionalItem);
}

function parseAdditionalItem(line) {
  const separatorIndex = line.indexOf(":");

  if (separatorIndex === -1) {
    return {
      label: line,
      value: "",
      visibleIn: ["concise", "detailed"],
    };
  }

  const rawLabel = line.slice(0, separatorIndex).trim();
  const { label, visibleIn } = parseAdditionalLabel(rawLabel);

  return {
    label,
    value: line.slice(separatorIndex + 1).trim(),
    visibleIn,
  };
}

function parseAdditionalLabel(label) {
  const [rawLabel, rawVisibleIn] = label.split("|", 2);

  return {
    label: rawLabel.trim(),
    visibleIn: parseVisibleIn(rawVisibleIn),
  };
}

function extractRequiredSection(source, startMarker, endMarker, options = {}) {
  const section = extractOptionalSection(
    source,
    startMarker,
    endMarker,
    options,
  );

  if (!section) {
    throw new Error(`Resume markdown section is missing: ${startMarker}.`);
  }

  return section;
}

function extractOptionalSection(source, startMarker, endMarker, options = {}) {
  const startIndex = source.indexOf(startMarker);

  if (startIndex === -1) {
    return null;
  }

  const requireEndMarker = options.requireEndMarker ?? Boolean(endMarker);
  const contentStart = startIndex + startMarker.length;
  const endIndex = endMarker ? source.indexOf(endMarker, contentStart) : -1;

  if (endMarker && endIndex === -1 && requireEndMarker) {
    return null;
  }

  return source.slice(contentStart, endIndex === -1 ? undefined : endIndex);
}

function parseMetadata(block) {
  const data = {};

  for (const rawLine of block.split("\n")) {
    const line = rawLine.trim();
    const match = line.match(/^([a-zA-Z]+):\s*(.*)$/);

    if (match) {
      data[match[1]] = match[2];
    }
  }

  return {
    id: requireText(data.id, "id"),
    section: parseSection(data.section),
    visibleIn: parseVisibleIn(data.visibleIn),
    website: parseWebsiteVisibility(data.website),
    startDate: requireText(data.startDate, "startDate"),
    endDate: parseEndDate(data.endDate),
    title: requireText(data.title, "title"),
    organization: optionalText(data.organization),
    location: optionalText(data.location),
  };
}

function parseSection(value) {
  const supportedSections = ["experience", "education", "training"];

  if (supportedSections.includes(value)) {
    return value;
  }

  throw new Error(`Unsupported resume section: ${value ?? "missing"}.`);
}

function parseVisibleIn(value) {
  const normalized = optionalText(value);

  if (!normalized) {
    return ["concise", "detailed"];
  }

  const levels = normalized
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  const supportedLevels = ["concise", "detailed"];

  for (const level of levels) {
    if (!supportedLevels.includes(level)) {
      throw new Error(`Unsupported resume detail level: ${level}.`);
    }
  }

  return levels.length > 0 ? levels : ["concise", "detailed"];
}

function parseWebsiteVisibility(value) {
  const normalized = optionalText(value)?.toLowerCase();

  if (!normalized) {
    return true;
  }
  if (normalized === "true") {
    return true;
  }
  if (normalized === "false") {
    return false;
  }

  throw new Error(`Unsupported resume website visibility: ${value}.`);
}

function parseEndDate(value) {
  const normalized = optionalText(value);

  if (!normalized || normalized === "null" || normalized === "present") {
    return null;
  }

  return normalized;
}

function requireText(value, fieldName) {
  const normalized = optionalText(value);

  if (!normalized) {
    throw new Error(`Resume metadata field is missing: ${fieldName}.`);
  }

  return normalized;
}

function optionalText(value) {
  return value?.trim() || undefined;
}

function parseParagraphs(source) {
  return source
    .trim()
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.replace(/\n/g, " ").trim())
    .filter(Boolean);
}

function parseBullets(source) {
  const bullets = [];
  let activeBullet = "";

  for (const rawLine of source.trim().split("\n")) {
    const line = rawLine.trim();

    if (line.startsWith("- ")) {
      if (activeBullet) {
        bullets.push(activeBullet.trim());
      }

      activeBullet = line.slice(2).trim();
      continue;
    }

    if (line && activeBullet) {
      activeBullet = `${activeBullet} ${line}`;
    }
  }

  if (activeBullet) {
    bullets.push(activeBullet.trim());
  }

  return bullets;
}

function stripRagSections(source) {
  return source
    .replace(/\n## RAG\n[\s\S]*?(?=\n# Entries)/g, "")
    .replace(/\n### RAG\n[\s\S]*?(?=\n## |\n# Additional Sections|\s*$)/g, "");
}

function renderResumeSnapshot(data, detailLevel) {
  const lines = [
    `# ${detailLevel} resume snapshot`,
    "",
    "## Summary",
    ...data.summary[detailLevel].map((item) => `- ${item}`),
    "",
    "## Entries",
  ];

  for (const entry of data.entries) {
    if (!entry.visibleIn.includes(detailLevel)) {
      continue;
    }

    const bullets = entry[detailLevel];

    lines.push("", `### ${entry.title}`, `id: ${entry.id}`);

    for (const bullet of bullets) {
      lines.push(`- ${bullet}`);
    }
  }

  lines.push("", "## Additional Sections");

  for (const section of data.additionalSections) {
    const items = section.items.filter((item) => {
      return item.visibleIn.includes(detailLevel);
    });

    if (items.length === 0) {
      continue;
    }

    lines.push("", `### ${section.title}`);

    for (const item of items) {
      lines.push(`- ${item.label}: ${item.value}`);
    }
  }

  return `${lines.join("\n").trim()}\n`;
}

function runNoLeakFixtureTest() {
  const fixture = `
# Summary

## Concise

Visible concise summary.

## Detailed

Visible detailed summary.

## RAG

- ${RAG_ONLY_SENTINEL} summary.

# Entries

## Sample Entry

\`\`\`yaml
id: sample-entry
section: experience
startDate: 2024-01
endDate: 2024-02
title: Sample Entry
\`\`\`

### Concise

- Visible concise bullet.

### Detailed

- Visible detailed bullet.

### RAG

- ${RAG_ONLY_SENTINEL} entry.

## Hidden RAG Only Entry

\`\`\`yaml
id: hidden-rag-only-entry
section: experience
website: false
startDate: 2025-01
endDate: present
title: Hidden RAG Only Entry
\`\`\`

### Concise

<!-- no bullets -->

### Detailed

<!-- no bullets -->

### RAG

- ${RAG_ONLY_SENTINEL} hidden entry.

# Additional Sections

## Languages

- English: B1/B2
`;
  const data = parseResume(fixture, { ignoreRagSections: true });
  const concise = renderResumeSnapshot(data, "concise");
  const detailed = renderResumeSnapshot(data, "detailed");

  assertNoRagLeak(concise);
  assertNoRagLeak(detailed);
  assert.match(concise, /Visible concise bullet/);
  assert.match(detailed, /Visible detailed bullet/);
  assert.doesNotMatch(concise, /Hidden RAG Only Entry/);
  assert.doesNotMatch(detailed, /Hidden RAG Only Entry/);
}

function assertNoRagLeak(text) {
  assert.doesNotMatch(text, /### RAG/);
  assert.doesNotMatch(text, /## RAG/);
  assert.doesNotMatch(text, new RegExp(RAG_ONLY_SENTINEL));
  assert.doesNotMatch(text, /RAG-only/i);
}

function normalizeLineEndings(source) {
  return source.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function compareResumeEntries(left, right) {
  const order = {
    experience: 0,
    education: 1,
    training: 2,
  };

  const sectionOrderDifference = order[left.section] - order[right.section];

  if (sectionOrderDifference !== 0) {
    return sectionOrderDifference;
  }

  return getSortDate(right).localeCompare(getSortDate(left));
}

function getSortDate(entry) {
  return entry.endDate ?? entry.startDate;
}
