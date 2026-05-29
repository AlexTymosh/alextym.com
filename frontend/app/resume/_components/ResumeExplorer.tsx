"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import type {
  ResumeData,
  ResumeDetailLevel,
  ResumeSection,
} from "../../../content/resume";
import { ResumeTimeline } from "./ResumeTimeline";
import styles from "./ResumeTimeline.module.css";

type ResumeExplorerProps = {
  resumeData: ResumeData;
};

const DETAIL_LEVELS: { id: ResumeDetailLevel; label: string }[] = [
  { id: "concise", label: "Concise" },
  { id: "detailed", label: "Detailed" },
];

const SECTION_BUTTONS: { id: ResumeSection; label: string }[] = [
  { id: "experience", label: "Experience" },
  { id: "education", label: "Education" },
  { id: "training", label: "Training" },
];

const DEFAULT_SECTIONS: ResumeSection[] = ["experience", "education"];

const DOWNLOAD_LINKS: Record<ResumeDetailLevel, string> = {
  concise: "/resume/alex-tymoshenko-cv-concise.pdf",
  detailed: "/resume/alex-tymoshenko-cv-detailed.pdf",
};

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

  return (
    <div className={styles.explorer}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <h1>Alex Tymoshenko</h1>
        </div>

        <a
          className={styles.downloadLink}
          download
          href={DOWNLOAD_LINKS[detailLevel]}
        >
          Download {detailLevel === "concise" ? "concise" : "detailed"} CV
        </a>
      </header>

      <IntroText />

      <div className={styles.toolbar} aria-label="Resume controls">
        <ControlGroup label="Detail level">
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

        <ControlGroup label="Sections">
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
          Select at least one section to show resume entries.
        </p>
      )}
    </div>
  );
}

function IntroText() {
  return (
    <div className={styles.introText}>
      <p>
        Automation Engineer focused on Python, API integrations, ERP workflows,
        reporting automation, Excel-to-database migration, data pipelines, and
        operational dashboards.
      </p>

      <p>
        I offer a three-step approach: requirements and ROI analysis, rapid
        AI-assisted prototyping, then testing, deployment, and support.
      </p>
    </div>
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
