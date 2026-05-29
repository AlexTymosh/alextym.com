import { Fragment } from "react";
import type { ReactNode } from "react";
import type {
  ResumeDetailLevel,
  ResumeEntry,
  ResumeSection,
} from "../../../content/resume";
import styles from "./ResumeTimeline.module.css";

const YEAR_MONTH_PATTERN = /^(\d{4})-(0[1-9]|1[0-2])$/;
const YEAR_PATTERN = /^\d{4}$/;
const LINK_PATTERN = /\[([^\]]+)]\(([^)]+)\)/g;

const SECTION_LABELS: Record<ResumeSection, string> = {
  experience: "Work Experience",
  education: "Education",
  training: "Training",
};

export type ResumeTimelineProps = {
  entries: ResumeEntry[];
  detailLevel: ResumeDetailLevel;
};

export function ResumeTimeline({
  detailLevel,
  entries,
}: ResumeTimelineProps) {
  return (
    <div className={styles.timeline} aria-label="Resume timeline">
      {entries.map((entry, index) => {
        const previousEntry = entries[index - 1];
        const shouldShowSectionDivider =
          index === 0 || previousEntry?.section !== entry.section;
        const bullets = entry[detailLevel];

        return (
          <Fragment key={entry.id}>
            {shouldShowSectionDivider ? (
              <h2 className={styles.sectionDivider}>
                <span>{SECTION_LABELS[entry.section]}</span>
              </h2>
            ) : null}

            <article className={styles.item}>
              <small className={styles.period}>
                {formatResumePeriod(entry.startDate, entry.endDate)}
              </small>

              <div className={styles.entryBody}>
                <h2>{entry.title}</h2>

                {entry.organization || entry.location ? (
                  <div className={styles.meta}>
                    {[entry.organization, entry.location]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                ) : null}

                {bullets.length > 0 ? (
                  <ul className={styles.bullets}>
                    {bullets.map((bullet) => (
                      <li key={`${entry.id}-${bullet}`}>
                        {renderInlineLinks(bullet)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </article>
          </Fragment>
        );
      })}
    </div>
  );
}

function renderInlineLinks(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = new RegExp(LINK_PATTERN.source, "g");
  let cursor = 0;
  let match = pattern.exec(text);

  while (match) {
    const matchIndex = match.index;
    const [fullMatch, label, href] = match;

    if (matchIndex > cursor) {
      nodes.push(text.slice(cursor, matchIndex));
    }

    nodes.push(
      <a
        className={styles.inlineLink}
        href={href}
        key={`${href}-${matchIndex}`}
        rel={isExternalLink(href) ? "noreferrer" : undefined}
        target={isExternalLink(href) ? "_blank" : undefined}
      >
        {label}
      </a>,
    );

    cursor = matchIndex + fullMatch.length;
    match = pattern.exec(text);
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }

  return nodes.length > 0 ? nodes : [text];
}

function isExternalLink(href: string): boolean {
  return href.startsWith("http://") || href.startsWith("https://");
}

function formatResumeDate(date: string): string {
  const yearMonthMatch = date.match(YEAR_MONTH_PATTERN);

  if (yearMonthMatch) {
    const [, year, month] = yearMonthMatch;
    return `${month}/${year}`;
  }

  if (YEAR_PATTERN.test(date)) {
    return date;
  }

  return date;
}

function formatResumePeriod(startDate: string, endDate: string | null): string {
  if (!endDate) {
    return `${formatResumeDate(startDate)} – Present`;
  }

  if (startDate === endDate) {
    return formatResumeDate(startDate);
  }

  return `${formatResumeDate(startDate)} – ${formatResumeDate(endDate)}`;
}
