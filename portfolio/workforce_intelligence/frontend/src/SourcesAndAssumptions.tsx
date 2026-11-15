import { SOURCE_REGISTER } from "./assurance-register";
import styles from "./workforce-scaffold.module.css";

const TYPE_LABEL = {
  synthetic: "Synthetic data",
  "public-reference": "Public reference",
  "modelling-assumption": "Modelling assumption",
} as const;

/** A visible provenance register, with no externally sourced KPI values. */
export function SourcesAndAssumptions() {
  return (
    <section id="sources" className={styles.panel} aria-labelledby="sources-heading">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="sources-heading">Sources and assumptions</h2>
          <p>Trace how synthetic operational records, modelling choices and public context are used.</p>
        </div>
      </div>
      <p className={styles.caption}>
        Public references are context only; their URLs come from specification v1.2 and
        have not been independently revalidated for this release. No NHS records
        or public benchmark values feed the synthetic KPI calculations.
      </p>
      <div role="region" aria-label="Sources and assumptions">
        {SOURCE_REGISTER.map((entry) => (
          <details key={entry.code} className={styles.catalogueEntry}>
            <summary>{entry.item} · {TYPE_LABEL[entry.type]}</summary>
            <dl className={styles.auditValues}>
              <dt>Origin / structural assumption</dt><dd>{entry.provenance}</dd>
              <dt>Publication / observed period</dt><dd>{entry.period}</dd>
              <dt>Reference</dt>
              <dd>{entry.reference ? <a href={entry.reference}>{entry.reference}</a> : "Local synthetic source; no external URL"}</dd>
              <dt>Verification / accessed</dt><dd>{entry.verification}</dd>
              <dt>Implementation use</dt><dd>{entry.usedFor}</dd>
              <dt>Limitations</dt><dd>{entry.limitation}</dd>
            </dl>
          </details>
        ))}
      </div>
    </section>
  );
}
