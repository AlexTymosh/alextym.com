import type { MetricDefinition, Quality } from "./data-api";
import { displayCode } from "./format";
import { QUALITY_RULE_GUIDANCE } from "./assurance-register";
import { SourcesAndAssumptions } from "./SourcesAndAssumptions";
import styles from "./workforce-scaffold.module.css";

const lineage = [
  { title: "Operational", identifier: "employment_contracts · starter_events", description: "Workforce SQLite stores effective-dated FTE, dated recruitment events and the mutation audit." },
  { title: "Bronze", identifier: "bronze_employment_contracts · bronze_starter_events", description: "Source-grain views carry the dataset generation and revision into each report." },
  { title: "Silver", identifier: "silver_substantive_employment · silver_starters", description: "Conformed employment intervals and starter evidence reconcile to contracts, offers and dated starts." },
  { title: "Gold", identifier: "Executive metrics · gold_reviewed_survey_findings", description: "Governed reports compute KPIs from a consistent snapshot. The survey view requires valid evidence and an earlier review." },
];

export function DataArchitecture({ quality, metrics }: { quality: Quality; metrics: MetricDefinition[] }) {
  return (
    <div className={styles.stack}>
      <section id="data-lineage" className={styles.panel} aria-labelledby="lineage-heading">
        <div className={styles.sectionHeader}><div><h2 id="lineage-heading">From source records to reports</h2>
          <p>Workforce owns this SQLite dataset. Portfolio Lab manages identity and grants in Firestore.</p></div></div>
        <ol className={styles.lineage}>
          {lineage.map((layer) => <li key={layer.title}><h3>{layer.title}</h3>
            <code>{layer.identifier}</code><p>{layer.description}</p></li>)}
        </ol>
      </section>
      <section id="quality" className={styles.panel} aria-labelledby="quality-heading">
        <div className={styles.sectionHeader}><div><h2 id="quality-heading">Data quality checks</h2>
          <p>Checked against the active dataset revision.</p></div>
          <span className={quality.quality_status === "passed" ? styles.statusBadge : styles.warningBadge}>
            {quality.quality_status === "passed" ? "Passed" : "Review required"}
          </span>
        </div>
        <p className={styles.caption}>
          These are four source-to-Silver reconciliation checks, not a full validation
          of completeness, protected-characteristic quality or all Workforce KPIs.
          Counts describe affected records per rule and may overlap; do not sum them.
        </p>
        <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Data quality rule details">
          <table className={styles.table}>
            <thead><tr><th scope="col">Implemented check</th><th scope="col">Issues</th>
              <th scope="col">Potential metric impact</th><th scope="col">Suggested investigation</th></tr></thead>
            <tbody>{Object.entries(quality.issues).map(([code, count]) => {
              const guidance = QUALITY_RULE_GUIDANCE[code];
              return <tr key={code}>
                <th scope="row">{guidance?.title ?? displayCode(code)}</th>
                <td>{count}</td>
                <td>{guidance?.impact ?? "Review source and affected Gold outputs."}</td>
                <td>{guidance?.investigation ?? "Inspect source validity and lineage."}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>
        <p className={styles.caption}>
          Any nonzero check flags the current dataset for review. These impact descriptions
          are guidance, not proof that a particular reported KPI is wrong.
        </p>
      </section>
      <SourcesAndAssumptions />
      <section id="catalogue" className={styles.panel} aria-labelledby="metric-catalogue-heading">
        <div className={styles.sectionHeader}><h2 id="metric-catalogue-heading">Metric catalogue</h2></div>
        {metrics.map((metric) => <details key={metric.code} className={styles.catalogueEntry}>
          <summary>{metric.name}</summary><p>{metric.formula} · v{metric.version}</p><p>{metric.caveat}</p>
        </details>)}
      </section>
    </div>
  );
}
