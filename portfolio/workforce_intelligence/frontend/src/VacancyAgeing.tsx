import type { VacancyAgeingReport } from "./data-api";
import { displayCode, displayNumber } from "./format";
import styles from "./workforce-scaffold.module.css";

/** Approved-to-cutoff ageing of effective, still-open requisitions. */
export function VacancyAgeing({ ageing, onSelectVacancy }: {
  ageing: VacancyAgeingReport;
  onSelectVacancy: (id: string) => void;
}) {
  const { bands, total_open_requisitions: total, total_open_wte: wte, oldest_open: oldest } = ageing.ageing;
  return (
    <section id="vacancy-ageing" className={styles.panel} aria-labelledby="ageing-heading">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="ageing-heading">Vacancy ageing</h2>
          <p>{total} open requisitions · {displayNumber(wte)} remaining WTE at {ageing.ageing.as_of_date}</p>
        </div>
      </div>
      <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Vacancy ageing bands">
        <table className={styles.table}>
          <thead><tr><th scope="col">Time since approval</th><th scope="col">Open requests</th>
            <th scope="col">Remaining WTE</th></tr></thead>
          <tbody>{bands.map((band) => (
            <tr key={band.code}>
              <th scope="row">{band.label}</th>
              <td><div className={styles.barCell}><span>{band.requisitions}</span>
                <span aria-hidden="true" className={styles.barTrack}>
                  <span style={{ width: `${total ? 100 * band.requisitions / total : 0}%` }} />
                </span></div></td>
              <td>{displayNumber(band.open_wte)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {oldest.length > 0 && <>
        <h3 style={{ marginTop: 20 }}>Oldest open requisitions</h3>
        <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Oldest open vacancies">
          <table className={styles.table}>
            <thead><tr><th scope="col">Vacancy</th><th scope="col">Days</th>
              <th scope="col">Status</th><th scope="col">Remaining WTE</th><th scope="col">Details</th></tr></thead>
            <tbody>{oldest.map((item) => (
              <tr key={item.id}>
                <th scope="row">{item.title}</th><td>{item.age_days}</td>
                <td>{displayCode(item.status)}</td><td>{displayNumber(item.open_wte)}</td>
                <td><button type="button" className={styles.linkButton}
                  onClick={() => onSelectVacancy(item.id)}
                  aria-label={`View funnel for ${item.id}`}>View funnel</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </>}
      <p className={styles.caption}>Synthetic data. Age is calendar days since approval, not time since
        advertisement. Only approved, advertised and partially filled requests count; administrative
        closure and cancellation do not imply a hire. Each request counts once, even for multiple positions.
        The oldest 12 requests appear above; summary bands include every open request.</p>
    </section>
  );
}
