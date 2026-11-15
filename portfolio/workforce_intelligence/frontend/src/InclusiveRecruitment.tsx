import type { InclusiveRecruitmentReport, InclusiveRecruitmentGroup } from "./data-api";
import { displayCode, displayNumber } from "./format";
import styles from "./workforce-scaffold.module.css";

const DIMENSIONS: Record<string, string> = {
  age_band: "Age band",
  ethnicity_group: "Ethnicity group",
  disability_status: "Disability status",
};

function codeLabel(value: string): string {
  return value === "not-stated" ? "Not stated / unknown" : displayCode(value);
}

function count(value: number | null): string {
  return value === null ? "Not available" : displayNumber(value);
}

function percent(value: number | null): string {
  return value === null ? "Not available" : `${displayNumber(value)}%`;
}

function GroupRow({ group }: { group: InclusiveRecruitmentGroup }) {
  return (
    <tr>
      <th scope="row">{codeLabel(group.code)}</th>
      <td>{count(group.applications)}</td>
      <td>{count(group.screened)}</td>
      <td>{count(group.shortlisted)}</td>
      <td>{count(group.interviewed)}</td>
      <td>{count(group.offers_made)}</td>
      <td>{count(group.accepted_offers)}</td>
      <td>{count(group.starters)}</td>
      <td>{percent(group.representation_percent)}</td>
      <td>{percent(group.shortlisting_percent)}</td>
      <td>{percent(group.interview_percent)}</td>
      <td>{percent(group.offer_acceptance_percent)}</td>
      <td>{percent(group.appointment_percent)}</td>
    </tr>
  );
}

/** Only render server-released aggregates; never reconstruct hidden cells on the client. */
export function InclusiveRecruitment({ inclusive }: { inclusive: InclusiveRecruitmentReport }) {
  const { report } = inclusive;
  return (
    <section id="equality" className={styles.panel} aria-labelledby="equality-heading">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="equality-heading">Inclusive recruitment</h2>
          <p>All observed applications through {report.as_of_date}. Synthetic aggregated data only.</p>
        </div>
      </div>
      <p className={styles.caption}>
        This disclosure-controlled report is independent of the date and vacancy filters above.
        Small groups and reconstructable differences are suppressed by the server, not hidden by CSS.
        Threshold: {report.threshold} applications. Rates describe observed outcomes, not equal-opportunity conclusions.
      </p>
      <div className={styles.stack}>
        {report.dimensions.map((dimension) => (
          <section key={dimension.code} aria-labelledby={`inclusive-${dimension.code}`}>
            <h3 id={`inclusive-${dimension.code}`}>{DIMENSIONS[dimension.code] ?? displayCode(dimension.code)}</h3>
            {dimension.status !== "available" ? (
              <p className={styles.message} role="status">
                {dimension.status === "suppressed" ? "Suppressed" : "Not available"}: {dimension.message}
              </p>
            ) : (
              <div className={styles.tableScroll} tabIndex={0} role="region"
                aria-label={`${DIMENSIONS[dimension.code] ?? dimension.code} aggregated outcomes`}>
                <table className={styles.table}>
                  <thead><tr>
                    <th scope="col">Category</th>
                    <th scope="col">Applications</th>
                    <th scope="col">Screened</th>
                    <th scope="col">Shortlisted</th>
                    <th scope="col">Interviewed</th>
                    <th scope="col">Offers made</th>
                    <th scope="col">Offers accepted</th>
                    <th scope="col">Started</th>
                    <th scope="col">Representation</th>
                    <th scope="col">Shortlisting rate</th>
                    <th scope="col">Interview rate</th>
                    <th scope="col">Offer acceptance rate</th>
                    <th scope="col">Appointment rate</th>
                  </tr></thead>
                  <tbody>{dimension.groups.map((group) => <GroupRow key={group.code} group={group} />)}</tbody>
                </table>
              </div>
            )}
          </section>
        ))}
      </div>
      <p className={styles.caption}>
        The denominator for representation is all observed applications. Shortlisting and appointment
        rates use applications within each category; missing outcomes are not treated as completed hires.
        Do not compare these synthetic figures with published NHS WRES benchmarks.
      </p>
    </section>
  );
}
