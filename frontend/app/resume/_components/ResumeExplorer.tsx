"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import type {
  ResumeAdditionalSection,
  ResumeData,
  ResumeDetailLevel,
  ResumeSection,
} from "../../../content/resume";
import { recordResumeDownload } from "../../../lib/privacy-safe-analytics";
import { resumeConfig } from "../../../lib/project-config";
import { ResumeTimeline } from "./ResumeTimeline";
import styles from "./ResumeTimeline.module.css";

type ResumeExplorerProps = {
  resumeData: ResumeData;
};

type DetailLevelOption = { id: ResumeDetailLevel; label: string };
type SectionButton = { id: ResumeSection; label: string };

const DETAIL_LEVELS = resumeConfig.detailLevels as DetailLevelOption[];
const SECTION_BUTTONS = resumeConfig.sectionButtons as SectionButton[];
const DEFAULT_SECTIONS = resumeConfig.defaultSections as ResumeSection[];
const DOWNLOAD_FILE_NAME = `${resumeConfig.downloadFileNameBase}.pdf`;

export function ResumeExplorer({ resumeData }: ResumeExplorerProps) {
  const [detailLevel, setDetailLevel] =
    useState<ResumeDetailLevel>("concise");
  const [selectedSections, setSelectedSections] =
    useState<ResumeSection[]>(DEFAULT_SECTIONS);

  const visibleEntries = useMemo(() => {
    return resumeData.entries.filter((entry) => {
      return (
        selectedSections.includes(entry.section) &&
        getEntryVisibleIn(entry).includes(detailLevel)
      );
    });
  }, [detailLevel, resumeData.entries, selectedSections]);

  const visibleAdditionalSections = useMemo(() => {
    return resumeData.additionalSections
      .map((section) => {
        return {
          ...section,
          items: section.items.filter((item) => {
            return item.visibleIn.includes(detailLevel);
          }),
        };
      })
      .filter((section) => section.items.length > 0);
  }, [detailLevel, resumeData.additionalSections]);

  const downloadHref = getDownloadHref(detailLevel, selectedSections);

  return (
    <div className={styles.explorer}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <h1>{resumeConfig.pageHeading}</h1>
        </div>

        <a
          className={styles.downloadLink}
          download={DOWNLOAD_FILE_NAME}
          href={downloadHref}
          onClick={recordResumeDownload}
        >
          {formatDownloadLabel(detailLevel)}
        </a>
      </header>

      <IntroText paragraphs={resumeData.summary.concise} />

      <div className={styles.toolbar} aria-label={resumeConfig.controlsAriaLabel}>
        <ControlGroup label={resumeConfig.detailControlLabel}>
          {DETAIL_LEVELS.map((item) => (
            <button
              aria-pressed={detailLevel === item.id}
              className={getControlButtonClass(detailLevel === item.id)}
              key={item.id}
              onClick={() => setDetailLevel(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </ControlGroup>

        <ControlGroup label={resumeConfig.sectionsControlLabel}>
          {SECTION_BUTTONS.map((item) => {
            const isActive = selectedSections.includes(item.id);

            return (
              <button
                aria-pressed={isActive}
                className={getControlButtonClass(isActive)}
                key={item.id}
                onClick={() => {
                  setSelectedSections((currentSections) => {
                    return toggleSection(item.id, currentSections);
                  });
                }}
                type="button"
              >
                {item.label}
              </button>
            );
          })}
        </ControlGroup>
      </div>

      {visibleEntries.length > 0 ? (
        <ResumeTimeline entries={visibleEntries} detailLevel={detailLevel} />
      ) : (
        <p className={styles.emptyState} role="status">
          {resumeConfig.emptyState}
        </p>
      )}

      {visibleAdditionalSections.length > 0 ? (
        <AdditionalSections sections={visibleAdditionalSections} />
      ) : null}
    </div>
  );
}

function IntroText({ paragraphs }: { paragraphs: readonly string[] }) {
  return (
    <div className={styles.introText}>
      {paragraphs.map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
    </div>
  );
}

function AdditionalSections({
  sections,
}: Readonly<{
  sections: ResumeAdditionalSection[];
}>) {
  return (
    <section
      aria-label={resumeConfig.additionalSectionsAriaLabel}
      className={styles.additionalSections}
    >
      {sections.map((section) => (
        <div className={styles.additionalGroup} key={section.id}>
          <h2 className={styles.sectionDivider}>
            <span>{section.title}</span>
          </h2>

          <div className={styles.additionalItems}>
            {section.items.map((item) => (
              <article
                className={styles.item}
                key={`${section.id}-${item.label}`}
              >
                <small className={styles.period}>{item.label}</small>

                <div className={styles.entryBody}>
                  <p className={styles.additionalValue}>{item.value}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function ControlGroup({
  children,
  label,
}: Readonly<{
  children: ReactNode;
  label: string;
}>) {
  return (
    <div className={styles.controlGroup}>
      <span className={styles.controlLabel}>{label}</span>
      <div className={styles.segmentedControl}>{children}</div>
    </div>
  );
}

function getDownloadHref(
  detailLevel: ResumeDetailLevel,
  selectedSections: ResumeSection[],
): string {
  const params = new URLSearchParams({
    detail: detailLevel,
    sections: selectedSections.join(","),
  });

  return `/resume/download?${params.toString()}`;
}

function formatDownloadLabel(detailLevel: ResumeDetailLevel): string {
  return resumeConfig.downloadLabelTemplate.replace("{detail}", detailLevel);
}

function getEntryVisibleIn(entry: {
  visibleIn?: ResumeDetailLevel[];
}): ResumeDetailLevel[] {
  return entry.visibleIn ?? ["concise", "detailed"];
}

function toggleSection(
  section: ResumeSection,
  currentSections: ResumeSection[],
): ResumeSection[] {
  return currentSections.includes(section)
    ? currentSections.filter((item) => item !== section)
    : [...currentSections, section];
}

function getControlButtonClass(isActive: boolean): string {
  return isActive
    ? `${styles.controlButton} ${styles.controlButtonActive}`
    : styles.controlButton;
}
