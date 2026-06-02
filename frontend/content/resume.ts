import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export type ResumeDetailLevel = "concise" | "detailed";
export type ResumeSection = "experience" | "education" | "training";

export type ResumeEntry = {
  id: string;
  section: ResumeSection;
  visibleIn: ResumeDetailLevel[];
  startDate: string;
  endDate: string | null;
  title: string;
  organization?: string;
  location?: string;
  concise: string[];
  detailed: string[];
};

export type ResumeAdditionalItem = {
  label: string;
  value: string;
  visibleIn: ResumeDetailLevel[];
};

export type ResumeAdditionalSection = {
  id: string;
  title: string;
  items: ResumeAdditionalItem[];
};

export type ResumeData = {
  summary: Record<ResumeDetailLevel, string[]>;
  entries: ResumeEntry[];
  additionalSections: ResumeAdditionalSection[];
};

type ResumeMetadata = {
  id: string;
  section: ResumeSection;
  visibleIn: ResumeDetailLevel[];
  website: boolean;
  startDate: string;
  endDate: string | null;
  title: string;
  organization?: string;
  location?: string;
};

type ExtractSectionOptions = {
  requireEndMarker?: boolean;
};

const SECTION_SORT_ORDER: Record<ResumeSection, number> = {
  experience: 0,
  education: 1,
  training: 2,
};

const YAML_BLOCK_PATTERN = /```yaml\n([\s\S]*?)\n```/;
const ADDITIONAL_SECTION_PATTERN =
  /(?:^|\n\n)## ([^\n]+)\n\n([\s\S]*?)(?=\n\n## |\s*$)/g;
const SUMMARY_RAG_MARKER = "## RAG";
const ENTRY_RAG_MARKER = "### RAG";

export function getResumeData(): ResumeData {
  return getResumeDataFromMarkdown(readResumeMarkdown());
}

export function getResumeDataFromMarkdown(markdown: string): ResumeData {
  const normalizedMarkdown = normalizeLineEndings(markdown);
  const summary = parseSummary(normalizedMarkdown);
  const entries = parseEntries(normalizedMarkdown);
  const additionalSections = parseAdditionalSections(normalizedMarkdown);

  return {
    summary,
    entries: entries.sort(compareResumeEntries),
    additionalSections,
  };
}

function readResumeMarkdown(): string {
  const possiblePaths = [
    join(process.cwd(), "content", "resume.md"),
    join(process.cwd(), "frontend", "content", "resume.md"),
  ];

  const resumePath = possiblePaths.find((path) => existsSync(path));

  if (!resumePath) {
    throw new Error("Static resume markdown source was not found.");
  }

  return readFileSync(resumePath, "utf8");
}

function normalizeLineEndings(markdown: string): string {
  return markdown.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function parseSummary(markdown: string): ResumeData["summary"] {
  const summaryMarkdown = extractRequiredSection(
    markdown,
    "# Summary",
    "# Entries",
  );
  const concise = extractRequiredSection(
    summaryMarkdown,
    "## Concise",
    "## Detailed",
  );
  const detailed = extractRequiredSection(
    summaryMarkdown,
    "## Detailed",
    SUMMARY_RAG_MARKER,
    { requireEndMarker: false },
  );

  return {
    concise: parseParagraphs(concise),
    detailed: parseParagraphs(detailed),
  };
}

function parseEntries(markdown: string): ResumeEntry[] {
  const entriesMarkdown = extractRequiredSection(
    markdown,
    "# Entries",
    "# Additional Sections",
  );
  const entryBlocks = splitEntryBlocks(entriesMarkdown);
  const entries = entryBlocks.map(parseEntryBlock).filter(isResumeEntry);

  if (entries.length === 0) {
    throw new Error("No resume entries were parsed from resume.md.");
  }

  return entries;
}

function splitEntryBlocks(markdown: string): string[] {
  return markdown
    .trim()
    .split(/\n(?=## )/)
    .map((block) => block.trim())
    .filter((block) => block.startsWith("## "));
}

function parseEntryBlock(block: string): ResumeEntry | null {
  const yamlMatch = block.match(YAML_BLOCK_PATTERN);

  if (!yamlMatch) {
    throw new Error("Resume entry metadata block is missing.");
  }

  const conciseMarkdown = extractRequiredSection(
    block,
    "### Concise",
    "### Detailed",
  );
  const detailedMarkdown = extractRequiredSection(
    block,
    "### Detailed",
    ENTRY_RAG_MARKER,
    { requireEndMarker: false },
  );
  const { website, ...metadata } = parseMetadata(yamlMatch[1]);

  if (!website) {
    return null;
  }

  return {
    ...metadata,
    concise: parseBullets(conciseMarkdown),
    detailed: parseBullets(detailedMarkdown),
  };
}

function isResumeEntry(entry: ResumeEntry | null): entry is ResumeEntry {
  return entry !== null;
}

function parseAdditionalSections(markdown: string): ResumeAdditionalSection[] {
  const additionalMarkdown = extractOptionalSection(
    markdown,
    "# Additional Sections",
  );

  if (!additionalMarkdown) {
    return [];
  }

  return Array.from(
    additionalMarkdown.matchAll(ADDITIONAL_SECTION_PATTERN),
  ).map((match) => {
    const title = match[1].trim();

    return {
      id: title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
      title,
      items: parseAdditionalItems(match[2]),
    };
  });
}

function parseAdditionalItems(markdown: string): ResumeAdditionalItem[] {
  return markdown
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim())
    .map(parseAdditionalItem);
}

function parseAdditionalItem(line: string): ResumeAdditionalItem {
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

function parseAdditionalLabel(label: string): {
  label: string;
  visibleIn: ResumeDetailLevel[];
} {
  const [rawLabel, rawVisibleIn] = label.split("|", 2);

  return {
    label: rawLabel.trim(),
    visibleIn: parseVisibleIn(rawVisibleIn),
  };
}

function extractRequiredSection(
  markdown: string,
  startMarker: string,
  endMarker?: string,
  options?: ExtractSectionOptions,
): string {
  const section = extractOptionalSection(
    markdown,
    startMarker,
    endMarker,
    options,
  );

  if (!section) {
    throw new Error(`Resume markdown section is missing: ${startMarker}.`);
  }

  return section;
}

function extractOptionalSection(
  markdown: string,
  startMarker: string,
  endMarker?: string,
  options?: ExtractSectionOptions,
): string | null {
  const startIndex = markdown.indexOf(startMarker);

  if (startIndex === -1) {
    return null;
  }

  const requireEndMarker = options?.requireEndMarker ?? Boolean(endMarker);
  const contentStart = startIndex + startMarker.length;
  const endIndex = endMarker
    ? markdown.indexOf(endMarker, contentStart)
    : -1;

  if (endMarker && endIndex === -1 && requireEndMarker) {
    return null;
  }

  return markdown.slice(contentStart, endIndex === -1 ? undefined : endIndex);
}

function parseMetadata(block: string): ResumeMetadata {
  const data: Record<string, string> = {};

  for (const rawLine of block.split("\n")) {
    const line = rawLine.trim();
    const match = line.match(/^([a-zA-Z]+):\s*(.*)$/);

    if (match) {
      data[match[1]] = match[2];
    }
  }

  const section = parseSection(data.section);

  return {
    id: requireText(data.id, "id"),
    section,
    visibleIn: parseVisibleIn(data.visibleIn),
    website: parseWebsiteVisibility(data.website),
    startDate: requireText(data.startDate, "startDate"),
    endDate: parseEndDate(data.endDate),
    title: requireText(data.title, "title"),
    organization: optionalText(data.organization),
    location: optionalText(data.location),
  };
}

function parseSection(value: string | undefined): ResumeSection {
  const supportedSections: ResumeSection[] = [
    "experience",
    "education",
    "training",
  ];

  if (supportedSections.includes(value as ResumeSection)) {
    return value as ResumeSection;
  }

  throw new Error(`Unsupported resume section: ${value ?? "missing"}.`);
}

function parseVisibleIn(value: string | undefined): ResumeDetailLevel[] {
  const normalized = optionalText(value);

  if (!normalized) {
    return ["concise", "detailed"];
  }

  const levels = normalized
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  const supportedLevels: ResumeDetailLevel[] = ["concise", "detailed"];

  for (const level of levels) {
    if (!supportedLevels.includes(level as ResumeDetailLevel)) {
      throw new Error(`Unsupported resume detail level: ${level}.`);
    }
  }

  if (levels.length === 0) {
    return ["concise", "detailed"];
  }

  return levels as ResumeDetailLevel[];
}

function parseWebsiteVisibility(value: string | undefined): boolean {
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

function parseEndDate(value: string | undefined): string | null {
  const normalized = optionalText(value);

  if (!normalized || normalized === "null" || normalized === "present") {
    return null;
  }

  return normalized;
}

function requireText(value: string | undefined, fieldName: string): string {
  const normalized = optionalText(value);

  if (!normalized) {
    throw new Error(`Resume metadata field is missing: ${fieldName}.`);
  }

  return normalized;
}

function optionalText(value: string | undefined): string | undefined {
  const normalized = value?.trim();
  return normalized || undefined;
}

function parseParagraphs(markdown: string): string[] {
  return markdown
    .trim()
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.replace(/\n/g, " ").trim())
    .filter(Boolean);
}

function parseBullets(markdown: string): string[] {
  const bullets: string[] = [];
  let activeBullet = "";

  for (const rawLine of markdown.trim().split("\n")) {
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

function compareResumeEntries(left: ResumeEntry, right: ResumeEntry): number {
  const sectionOrderDifference =
    SECTION_SORT_ORDER[left.section] - SECTION_SORT_ORDER[right.section];

  if (sectionOrderDifference !== 0) {
    return sectionOrderDifference;
  }

  return getSortDate(right).localeCompare(getSortDate(left));
}

function getSortDate(entry: ResumeEntry): string {
  return entry.endDate ?? entry.startDate;
}
