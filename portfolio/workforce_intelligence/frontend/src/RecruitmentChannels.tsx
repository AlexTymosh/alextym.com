import type { RecruitmentSources } from "./data-api";
import { displayCode, displayNumber } from "./format";
import styles from "./workforce-scaffold.module.css";

type Props = {
  sources: RecruitmentSources;
  vacancyFiltered: boolean;
};

/** A cohort report: one application, not one event or one requisition. */
export function RecruitmentChannels({ sources, vacancyFiltered }: Props) {
  const { report } = sources;
  const total = report.total_applications;

  return (
    <section id="attraction" className={styles.panel} aria-labelledby="attraction-heading">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="attraction-heading">Recruitment channels</h2>
          <p>{total} unique applications received in the selected period, grouped by source.</p>
        </div>
      </div>
      {vacancyFiltered && (
        <p className={styles.caption}>
          Channel totals cover all vacancies. The vacancy selector above applies only to the candidate funnel.
        </p>
      )}
      {total > 0 ? (
        <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Recruitment channel table">
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Applications</th>
                <th scope="col">Screened</th>
                <th scope="col">Shortlisted</th>
                <th scope="col">Interviewed</th>
                <th scope="col">Offers accepted</th>
                <th scope="col">Started</th>
                <th scope="col">Application → start</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <tr key={row.source_code}>
                  <th scope="row">{displayCode(row.source_code)}</th>
                  <td>
                    <div className={styles.barCell}>
                      <span>{row.applications}</span>
                      <span aria-hidden="true" className={styles.barTrack}>
                        <span style={{ width: `${row.applications / total * 100}%` }} />
                      </span>
                    </div>
                  </td>
                  <td>{row.screened}</td>
                  <td>{row.shortlisted}</td>
                  <td>{row.interviewed}</td>
                  <td>{row.accepted_offers}</td>
                  <td>{row.starters}</td>
                  <td>{row.application_to_start_percent === null
                    ? "Not available"
                    : `${displayNumber(row.application_to_start_percent)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={styles.message}>There are no applications in this reporting window.</p>
      )}
      <p className={styles.caption}>
        Synthetic data. Conversion is observed by the selected cutoff, not a completed-cohort outcome.
        Recent applications have had less time to progress. Vacancy counts are not used as denominators.
      </p>
    </section>
  );
}
