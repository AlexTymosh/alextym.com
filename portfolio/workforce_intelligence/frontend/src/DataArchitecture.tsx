import type { MetricDefinition, Quality } from "./data-api";
import { displayCode } from "./format";
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
        <dl className={styles.summaryFacts}>{Object.entries(quality.issues).map(([check, count]) => (
          <div key={check}><dt>{displayCode(check)}</dt><dd>{count}</dd></div>
        ))}</dl>
      </section>
      <section id="catalogue" className={styles.panel} aria-labelledby="metric-catalogue-heading">
        <div className={styles.sectionHeader}><h2 id="metric-catalogue-heading">Metric catalogue</h2></div>
        {metrics.map((metric) => <details key={metric.code} className={styles.catalogueEntry}>
          <summary>{metric.name}</summary><p>{metric.formula} · v{metric.version}</p><p>{metric.caveat}</p>
        </details>)}
      </section>
    </div>
  );
}
