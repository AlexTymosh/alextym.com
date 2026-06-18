import type {
  ResumeAdditionalSection,
  ResumeData,
  ResumeDetailLevel,
  ResumeEntry,
  ResumeSection,
} from "./resume";
import {
  getPublicLink,
  resumeConfig,
  siteIdentityConfig,
} from "../lib/project-config";

export type ResumePdfOptions = {
  detailLevel: ResumeDetailLevel;
  sections: ResumeSection[];
};

type PdfTextSegment = {
  text: string;
  href?: string;
};

type PdfSkill = {
  label: string;
  value: string;
};

type PdfLink = {
  x: number;
  y: number;
  width: number;
  height: number;
  href: string;
};

type PdfPageDraft = {
  commands: string[];
  links: PdfLink[];
};

type PdfObject = {
  body: string;
};

type PdfColor = "black" | "link" | "teal";
type PdfFont = "F1" | "F2";

const PAGE_WIDTH = 595;
const PAGE_HEIGHT = 842;
const MARGIN_X = 31;
const MARGIN_TOP = 37;
const MARGIN_BOTTOM = 42;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN_X * 2;
const PDF_LINK_SEPARATOR = ` ${"\u2022"} `;
const resumePdfConfig = resumeConfig.pdf;
const DOWNLOAD_FILE_NAME = `${resumeConfig.downloadFileNameBase}.pdf`;

const SECTION_LABELS =
  resumePdfConfig.sectionLabels as Record<ResumeSection, string>;

const SUPPORTED_SECTIONS: ResumeSection[] = [
  "experience",
  "education",
  "training",
];

const DEFAULT_SECTIONS: ResumeSection[] = ["experience", "education"];

const HEADER_LINKS = withPdfLinkSeparators(buildHeaderLinks());
const ROLE_TITLE = resumePdfConfig.roleTitle;
const CONTACT_NOTE_FIRST = resumePdfConfig.contactNote.first;
const CONTACT_NOTE_SECOND =
  resumePdfConfig.contactNote.second as PdfTextSegment[];
const SKILLS = resumePdfConfig.skills as PdfSkill[];

const HELVETICA_WIDTHS: Record<string, number> = {
  " ": 278,
  "!": 278,
  '"': 355,
  "#": 556,
  "$": 556,
  "%": 889,
  "&": 667,
  "'": 191,
  "(": 333,
  ")": 333,
  "*": 389,
  "+": 584,
  ",": 278,
  "-": 333,
  ".": 278,
  "/": 278,
  "0": 556,
  "1": 556,
  "2": 556,
  "3": 556,
  "4": 556,
  "5": 556,
  "6": 556,
  "7": 556,
  "8": 556,
  "9": 556,
  ":": 278,
  ";": 278,
  "<": 584,
  "=": 584,
  ">": 584,
  "?": 556,
  "@": 1015,
  A: 667,
  B: 667,
  C: 722,
  D: 722,
  E: 667,
  F: 611,
  G: 778,
  H: 722,
  I: 278,
  J: 500,
  K: 667,
  L: 556,
  M: 833,
  N: 722,
  O: 778,
  P: 667,
  Q: 778,
  R: 722,
  S: 667,
  T: 611,
  U: 722,
  V: 667,
  W: 944,
  X: 667,
  Y: 667,
  Z: 611,
  "[": 278,
  "\\": 278,
  "]": 278,
  "^": 469,
  _: 556,
  "`": 333,
  a: 556,
  b: 556,
  c: 500,
  d: 556,
  e: 556,
  f: 278,
  g: 556,
  h: 556,
  i: 222,
  j: 222,
  k: 500,
  l: 222,
  m: 833,
  n: 556,
  o: 556,
  p: 556,
  q: 556,
  r: 333,
  s: 500,
  t: 278,
  u: 556,
  v: 500,
  w: 722,
  x: 500,
  y: 500,
  z: 500,
  "{": 334,
  "|": 260,
  "}": 334,
  "~": 584,
  "•": 350,
};

export function parseResumePdfOptions(
  searchParams: URLSearchParams,
): ResumePdfOptions {
  const rawDetailLevel = searchParams.get("detail") ?? "concise";
  const detailLevel = parseDetailLevel(rawDetailLevel);
  const sections = parseSections(searchParams.get("sections"));

  return {
    detailLevel,
    sections,
  };
}

export function getResumePdfFileName(): string {
  return DOWNLOAD_FILE_NAME;
}

export function buildResumePdf(
  resumeData: ResumeData,
  options: ResumePdfOptions,
): Uint8Array {
  const entries = getVisibleEntries(resumeData, options);
  const additionalSections = getVisibleAdditionalSections(resumeData, options);
  const document = new PdfTextDocument(options.detailLevel);

  renderHeader(document, resumeData);
  renderSkills(document);
  renderResumeEntries(document, entries);
  renderAdditionalSections(document, additionalSections);

  return document.toPdfBytes();
}

function parseDetailLevel(value: string): ResumeDetailLevel {
  return value === "detailed" ? "detailed" : "concise";
}

function parseSections(value: string | null): ResumeSection[] {
  if (!value) {
    return DEFAULT_SECTIONS;
  }

  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item): item is ResumeSection => {
      return SUPPORTED_SECTIONS.includes(item as ResumeSection);
    });
}

function getVisibleEntries(
  resumeData: ResumeData,
  options: ResumePdfOptions,
): ResumeEntry[] {
  return resumeData.entries.filter((entry) => {
    return (
      options.sections.includes(entry.section) &&
      entry.visibleIn.includes(options.detailLevel)
    );
  });
}

function getVisibleAdditionalSections(
  resumeData: ResumeData,
  options: ResumePdfOptions,
): ResumeAdditionalSection[] {
  return resumeData.additionalSections
    .map((section) => {
      return {
        ...section,
        items: section.items.filter((item) => {
          return item.visibleIn.includes(options.detailLevel);
        }),
      };
    })
    .filter((section) => section.items.length > 0);
}

function withPdfLinkSeparators(
  segments: readonly PdfTextSegment[],
): PdfTextSegment[] {
  return segments.flatMap((segment, index) => {
    if (index === 0) {
      return [segment];
    }

    return [{ text: PDF_LINK_SEPARATOR }, segment];
  });
}

function buildHeaderLinks(): PdfTextSegment[] {
  const visibility = resumePdfConfig.headerLinkVisibility as Record<string, boolean>;
  const segments: PdfTextSegment[] = [];

  if (visibility.website) {
    segments.push({
      href: ensureTrailingSlash(siteIdentityConfig.canonicalUrl),
      text: getWebsiteDisplayText(siteIdentityConfig.canonicalUrl),
    });
  }

  for (const key of ["linkedin", "github", "facebook"]) {
    if (!visibility[key]) {
      continue;
    }

    const link = getPublicLink(key);
    if (link) {
      segments.push({
        href: link.href,
        text: link.label,
      });
    }
  }

  if (visibility.rightToWorkUk) {
    segments.push({ text: "Right to work in UK" });
  }

  return segments;
}

function getWebsiteDisplayText(value: string): string {
  try {
    return new URL(value).hostname;
  } catch {
    return value.replace(/^https?:\/\//, "").replace(/\/+$/, "");
  }
}

function ensureTrailingSlash(value: string): string {
  return value.endsWith("/") ? value : `${value}/`;
}

function renderHeader(document: PdfTextDocument, resumeData: ResumeData): void {
  document.addText(resumePdfConfig.displayName, {
    color: "teal",
    font: "F1",
    leading: 22,
    size: 15,
  });
  document.addText(ROLE_TITLE, {
    color: "teal",
    font: "F1",
    leading: 18,
    size: 12,
  });
  document.addRule();
  document.addGap(12);
  document.addSegments(HEADER_LINKS, {
    leading: 14,
    size: 8.5,
  });
  document.addGap(9);
  document.addNote(
    resumePdfConfig.noteLabel,
    CONTACT_NOTE_FIRST,
    CONTACT_NOTE_SECOND,
  );
  document.addGap(9);
  document.addParagraph(getResumeProfileText(resumeData), {
    leading: 13,
    size: 9.4,
  });
}

function getResumeProfileText(resumeData: ResumeData): string {
  return resumeData.summary.concise.join(" ");
}

function renderSkills(document: PdfTextDocument): void {
  document.addSectionHeading(resumePdfConfig.skillsHeading);

  for (const skill of SKILLS) {
    document.addLabelParagraph(skill.label, skill.value);
  }
}

function renderResumeEntries(
  document: PdfTextDocument,
  entries: ResumeEntry[],
): void {
  let previousSection: ResumeSection | null = null;

  for (const entry of entries) {
    if (entry.section !== previousSection) {
      document.addSectionHeading(SECTION_LABELS[entry.section]);
      previousSection = entry.section;
    }

    renderEntry(document, entry);
  }
}

function renderEntry(document: PdfTextDocument, entry: ResumeEntry): void {
  document.addParagraph(`${formatPeriod(entry)} ${plainText(entry.title)}`, {
    font: "F2",
    leading: 13,
    size: 9.5,
  });

  const metadata = [entry.organization, entry.location]
    .filter(Boolean)
    .map((item) => plainText(item ?? ""))
    .join(" - ");

  if (metadata) {
    document.addParagraph(metadata, {
      leading: 10,
      size: 8.5,
    });
  }

  for (const bullet of entry[document.detailLevel]) {
    document.addParagraph(`- ${plainText(bullet)}`, {
      indent: 10,
      leading: 10.5,
      size: 8.5,
    });
  }

  document.addGap(2);
}

function renderAdditionalSections(
  document: PdfTextDocument,
  sections: ResumeAdditionalSection[],
): void {
  for (const section of sections) {
    document.addSectionHeading(section.title.toUpperCase());

    for (const item of section.items) {
      const value = item.value ? `${item.label}: ${item.value}` : item.label;

      document.addParagraph(value, {
        leading: 10.5,
        size: 8.5,
      });
    }
  }
}

function plainText(value: string): string {
  return value.replace(/\[([^\]]+)]\(([^)]+)\)/g, "$1");
}

function formatPeriod(entry: ResumeEntry): string {
  const startDate = formatResumeDate(entry.startDate);

  if (!entry.endDate) {
    return `${startDate} - ${resumePdfConfig.presentLabel}`;
  }

  const endDate = formatResumeDate(entry.endDate);
  return startDate === endDate ? startDate : `${startDate} - ${endDate}`;
}

function formatResumeDate(value: string): string {
  const match = value.match(/^(\d{4})-(0[1-9]|1[0-2])$/);

  if (!match) {
    return value;
  }

  return `${match[2]}/${match[1]}`;
}

class PdfTextDocument {
  readonly detailLevel: ResumeDetailLevel;
  private pages: PdfPageDraft[] = [];
  private y = PAGE_HEIGHT - MARGIN_TOP;

  constructor(detailLevel: ResumeDetailLevel) {
    this.detailLevel = detailLevel;
    this.addPage();
  }

  addText(
    value: string,
    options: {
      color?: PdfColor;
      font?: PdfFont;
      leading?: number;
      size?: number;
    } = {},
  ): void {
    const font = options.font ?? "F1";
    const leading = options.leading ?? 12;
    const size = options.size ?? 9;
    this.ensureSpace(leading);
    this.currentPage().commands.push(colorCommand(options.color ?? "black"));
    this.currentPage().commands.push(
      textCommand(font, size, MARGIN_X, this.y, value),
    );
    this.currentPage().commands.push(colorCommand("black"));
    this.y -= leading;
  }

  addSegments(
    segments: PdfTextSegment[],
    options: {
      leading?: number;
      size?: number;
      x?: number;
    } = {},
  ): void {
    const leading = options.leading ?? 12;
    const size = options.size ?? 9;
    let x = options.x ?? MARGIN_X;

    this.ensureSpace(leading);

    for (const segment of segments) {
      const width = estimateTextWidth(segment.text, size, "F1");

      if (segment.href) {
        this.currentPage().commands.push(colorCommand("link"));
      }

      this.currentPage().commands.push(
        textCommand("F1", size, x, this.y, segment.text),
      );

      if (segment.href) {
        this.addLinkUnderline(x, this.y, width);
        this.currentPage().commands.push(colorCommand("black"));
        this.currentPage().links.push({
          height: size + 3,
          href: segment.href,
          width,
          x,
          y: this.y - 2,
        });
      }

      x += width;
    }

    this.y -= leading;
  }

  addNote(
    label: string,
    firstSentence: string,
    secondSentence: PdfTextSegment[],
  ): void {
    const size = 9.4;
    const labelWidth = estimateTextWidth(label, size, "F1");
    const textX = MARGIN_X + labelWidth + 7;

    this.ensureSpace(26);
    this.currentPage().commands.push(
      textCommand("F1", size, MARGIN_X, this.y, label),
    );
    this.addLinkUnderline(MARGIN_X, this.y, labelWidth);
    this.currentPage().commands.push(
      textCommand("F1", size, textX, this.y, firstSentence),
    );

    this.y -= 13;
    this.addSegments(secondSentence, {
      leading: 13,
      size,
      x: textX,
    });
  }

  addParagraph(
    value: string,
    options: {
      font?: PdfFont;
      indent?: number;
      leading?: number;
      size?: number;
    } = {},
  ): void {
    const font = options.font ?? "F1";
    const indent = options.indent ?? 0;
    const leading = options.leading ?? 11;
    const size = options.size ?? 8.7;
    const width = CONTENT_WIDTH - indent;
    const lines = wrapText(value, width, size, font);

    for (const line of lines) {
      this.ensureSpace(leading);
      this.currentPage().commands.push(
        textCommand(font, size, MARGIN_X + indent, this.y, line),
      );
      this.y -= leading;
    }
  }

  addLabelParagraph(label: string, value: string): void {
    const size = 8.8;
    const labelText = `${label}:`;
    const labelWidth = estimateTextWidth(labelText, size, "F2");
    const valueX = MARGIN_X + labelWidth + 8;
    const width = PAGE_WIDTH - valueX - MARGIN_X;
    const lines = wrapText(value, width, size, "F1");
    let firstLine = true;

    for (const line of lines) {
      this.ensureSpace(11);

      if (firstLine) {
        this.currentPage().commands.push(
          textCommand("F2", size, MARGIN_X, this.y, labelText),
        );
      }

      this.currentPage().commands.push(
        textCommand("F1", size, firstLine ? valueX : MARGIN_X, this.y, line),
      );
      this.y -= 11;
      firstLine = false;
    }
  }

  addSectionHeading(value: string): void {
    this.addGap(7);
    this.ensureSpace(23);
    this.currentPage().commands.push(colorCommand("teal"));
    this.currentPage().commands.push(
      textCommand("F1", 12, MARGIN_X, this.y, value),
    );
    this.currentPage().commands.push(colorCommand("black"));
    this.y -= 7;
    this.addRule();
    this.y -= 12;
  }

  addRule(): void {
    this.ensureSpace(2);
    this.currentPage().commands.push(
      `0.2 0.2 0.2 RG ${MARGIN_X} ${this.y} m ${PAGE_WIDTH - MARGIN_X} ${this.y} l S`,
    );
  }

  addGap(value: number): void {
    this.y -= value;
  }

  toPdfBytes(): Uint8Array {
    const objects: PdfObject[] = [];
    const pageRefs: number[] = [];

    objects.push({
      body: "<< /Type /Catalog /Pages 2 0 R >>",
    });
    objects.push({
      body: "__PAGES__",
    });
    objects.push({
      body: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    });
    objects.push({
      body: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    });

    for (const page of this.pages) {
      const content = page.commands.join("\n");
      const contentRef = objects.length + 1;

      objects.push({
        body: [
          `<< /Length ${Buffer.byteLength(content, "utf8")} >>`,
          "stream",
          content,
          "endstream",
        ].join("\n"),
      });

      const annotationRefs: number[] = [];

      for (const link of page.links) {
        annotationRefs.push(objects.length + 1);
        objects.push({
          body: linkAnnotationBody(link),
        });
      }

      const pageRef = objects.length + 1;
      pageRefs.push(pageRef);
      objects.push({
        body: pageBody(contentRef, annotationRefs),
      });
    }

    objects[1] = {
      body: [
        `<< /Type /Pages /Count ${pageRefs.length}`,
        `/Kids [${pageRefs.map((ref) => `${ref} 0 R`).join(" ")}] >>`,
      ].join(" "),
    };

    return buildPdf(objects);
  }

  private addLinkUnderline(x: number, y: number, width: number): void {
    const underlineY = y - 1.5;
    this.currentPage().commands.push(
      `${x} ${underlineY} m ${x + width} ${underlineY} l S`,
    );
  }

  private addPage(): void {
    this.pages.push({
      commands: ["0 0 0 rg 0 0 0 RG", "0.15 w"],
      links: [],
    });
    this.y = PAGE_HEIGHT - MARGIN_TOP;
  }

  private currentPage(): PdfPageDraft {
    return this.pages[this.pages.length - 1];
  }

  private ensureSpace(requiredHeight: number): void {
    if (this.y - requiredHeight < MARGIN_BOTTOM) {
      this.addPage();
    }
  }
}

function colorCommand(color: PdfColor): string {
  if (color === "link") {
    return "0.043 0.267 0.333 rg 0.043 0.267 0.333 RG";
  }

  if (color === "teal") {
    return "0.043 0.267 0.333 rg 0.043 0.267 0.333 RG";
  }

  return "0 0 0 rg 0 0 0 RG";
}

function textCommand(
  font: PdfFont,
  size: number,
  x: number,
  y: number,
  value: string,
): string {
  return `BT /${font} ${size} Tf ${x} ${y} Td (${pdfText(value)}) Tj ET`;
}

function pageBody(contentRef: number, annotationRefs: number[]): string {
  const annotations =
    annotationRefs.length > 0
      ? ` /Annots [${annotationRefs.map((ref) => `${ref} 0 R`).join(" ")}]`
      : "";

  return [
    "<< /Type /Page /Parent 2 0 R",
    `/MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}]`,
    "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >>",
    `/Contents ${contentRef} 0 R${annotations} >>`,
  ].join(" ");
}

function linkAnnotationBody(link: PdfLink): string {
  const x2 = link.x + link.width;
  const y2 = link.y + link.height;

  return [
    "<< /Type /Annot /Subtype /Link",
    `/Rect [${link.x} ${link.y} ${x2} ${y2}]`,
    "/Border [0 0 0]",
    `/A << /S /URI /URI (${pdfText(link.href)}) >> >>`,
  ].join(" ");
}

function buildPdf(objects: PdfObject[]): Uint8Array {
  let output = "%PDF-1.4\n";
  const offsets = [0];

  for (let index = 0; index < objects.length; index += 1) {
    offsets.push(Buffer.byteLength(output, "utf8"));
    output += `${index + 1} 0 obj\n${objects[index].body}\nendobj\n`;
  }

  const xrefOffset = Buffer.byteLength(output, "utf8");

  output += `xref\n0 ${objects.length + 1}\n`;
  output += "0000000000 65535 f \n";

  for (let index = 1; index < offsets.length; index += 1) {
    output += `${offsets[index].toString().padStart(10, "0")} 00000 n \n`;
  }

  output += [
    "trailer",
    `<< /Size ${objects.length + 1} /Root 1 0 R >>`,
    "startxref",
    String(xrefOffset),
    "%%EOF",
  ].join("\n");

  return new Uint8Array(Buffer.from(output, "utf8"));
}

function wrapText(
  value: string,
  width: number,
  size: number,
  font: PdfFont,
): string[] {
  const words = sanitizeText(value).split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let activeLine = "";

  for (const word of words) {
    const candidate = activeLine ? `${activeLine} ${word}` : word;

    if (estimateTextWidth(candidate, size, font) <= width) {
      activeLine = candidate;
      continue;
    }

    if (activeLine) {
      lines.push(activeLine);
    }

    activeLine = word;
  }

  if (activeLine) {
    lines.push(activeLine);
  }

  return lines.length > 0 ? lines : [""];
}

function estimateTextWidth(value: string, size: number, font: PdfFont): number {
  const fontFactor = font === "F2" ? 1.07 : 1;
  let width = 0;

  for (const char of sanitizeText(value)) {
    width += (HELVETICA_WIDTHS[char] ?? 556) * size * fontFactor;
  }

  return width / 1000;
}

function pdfText(value: string): string {
  let output = "";

  for (const char of sanitizeText(value)) {
    if (char === "\\") {
      output += "\\\\";
      continue;
    }

    if (char === "(") {
      output += "\\(";
      continue;
    }

    if (char === ")") {
      output += "\\)";
      continue;
    }

    if (char === "•") {
      output += "\\225";
      continue;
    }

    output += char;
  }

  return output;
}

function sanitizeText(value: string): string {
  return value
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/[–—]/g, "-")
    .replace(/→/g, "->")
    .replace(/·/g, "-")
    .replace(/[^\x20-\x7E•]/g, "");
}
