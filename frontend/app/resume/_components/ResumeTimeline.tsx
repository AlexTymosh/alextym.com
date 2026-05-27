import type { ResumeEntry } from "../../../content/resume";
import styles from "./ResumeTimeline.module.css";

const YEAR_MONTH_PATTERN = /^(\d{4})-(0[1-9]|1[0-2])$/;
const YEAR_PATTERN = /^\d{4}$/;

function formatResumeDate(date: string) {
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

function formatResumePeriod(startDate: string, endDate: string | null) {
  return `${formatResumeDate(startDate)} – ${endDate ? formatResumeDate(endDate) : "Present"}`;
}

type ResumeTimelineProps = {
  entries: ResumeEntry[];
};

export function ResumeTimeline({ entries }: ResumeTimelineProps) {
  return (
    <div className="resume-timeline" aria-label="Resume highlights">
      {entries.map((entry) => (
        <article key={entry.id} className="resume-timeline__item">
          <span className="resume-timeline__marker" aria-hidden="true" />
          <small>{formatResumePeriod(entry.startDate, entry.endDate)}</small>
          <h2>{entry.title}</h2>

          {entry.company || entry.location ? (
            <div className={styles.meta}>{[entry.company, entry.location].filter(Boolean).join(" · ")}</div>
          ) : null}

          <ul className={styles.bullets}>
            {entry.bullets.map((bullet, index) => (
              <li key={`${entry.id}-${index}`}>{bullet}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
