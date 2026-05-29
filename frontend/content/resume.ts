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

export type ResumeData = {
  summary: Record<ResumeDetailLevel, string[]>;
  entries: ResumeEntry[];
};

type ResumeMetadata = {
  id: string;
  section: ResumeSection;
  visibleIn: ResumeDetailLevel[];
  startDate: string;
  endDate: string | null;
  title: string;
  organization?: string;
  location?: string;
};

const SECTION_SORT_ORDER: Record<ResumeSection, number> = {
  experience: 0,
  education: 1,
  training: 2,
};

const ENTRY_PATTERN = new RegExp(
  [
    "(?:^|\\n\\n)## .+\\n\\n```yaml\\n([\\s\\S]*?)\\n```",
    "\\n\\n### Concise\\n([\\s\\S]*?)",
    "\\n\\n### Detailed\\n([\\s\\S]*?)(?=\\n\\n## |\\s*$)",
  ].join(""),
  "g",
);

const SUMMARY_PATTERN =
  /# Summary\n\n## Concise\n([\s\S]*?)\n\n## Detailed\n([\s\S]*?)\n\n# Entries/;

export function getResumeData(): ResumeData {
  const markdown = readResumeMarkdown();
  const summary = parseSummary(markdown);
  const entries = parseEntries(markdown);

  return {
    summary,
    entries: entries.sort(compareResumeEntries),
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

function parseSummary(markdown: string): ResumeData["summary"] {
  const match = markdown.match(SUMMARY_PATTERN);

  if (!match) {
    throw new Error("Resume summary sections are missing or malformed.");
  }

  return {
    concise: parseParagraphs(match[1]),
    detailed: parseParagraphs(match[2]),
  };
}

function parseEntries(markdown: string): ResumeEntry[] {
  const entriesMarkdown = markdown.split("# Entries")[1];

  if (!entriesMarkdown) {
    throw new Error("Resume entries section is missing.");
  }

  const entries = Array.from(entriesMarkdown.matchAll(ENTRY_PATTERN)).map(
    (match) => {
      const metadata = parseMetadata(match[1]);

      return {
        ...metadata,
        concise: parseBullets(match[2]),
        detailed: parseBullets(match[3]),
      };
    },
  );

  if (entries.length === 0) {
    throw new Error("No resume entries were parsed from resume.md.");
  }

  return entries;
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
