import { useState } from "react";
import type { Architecture, MetricDefinition } from "./data-api";
import { DataModel } from "./DataModel";
import { displayCode, displayDay, displayNumber } from "./format";
import { QUALITY_RULE_GUIDANCE } from "./assurance-register";
import { SourcesAndAssumptions } from "./SourcesAndAssumptions";
import { VoiceProcess } from "./VoiceProcess";
import styles from "./workforce-scaffold.module.css";

const lineage = {
  operational: {
    title: "Operational", purpose: "Capture approved synthetic source changes.",
    content: "Effective-dated contracts, recruitment events, survey campaign records and import audit.",
    transform: "The UI and validated workbooks create source rows under transaction and version checks.",
    owner: "People Team",
  },
  bronze: {
    title: "Bronze", purpose: "Expose accepted source rows with lineage.",
    content: "Source-grain synthetic records and dataset metadata.",
    transform: "Views add the dataset generation and source revision. Source grain is preserved.",
    owner: "Data & Analytics",
  },
  silver: {
    title: "Silver", purpose: "Conform effective dates and keys for analysis.",
    content: "Valid employment intervals, applications, offers, starter events and dimensions.",
    transform: "Intersect contracts with assignments and reconcile starters to accepted offers and effective employment.",
    owner: "Data & Analytics",
  },
  gold: {
    title: "Gold", purpose: "Publish governed metrics and evidence-backed findings.",
    content: "Aggregate KPIs, registered comparisons, forecast results and reviewed survey findings.",
    transform: "Calculate metrics at the cutoff. People Voice admits only evidence-linked findings with a prior review and explicit publication.",
    owner: "Analyst Reviewer",
  },
};

export function DataArchitecture({ architecture, metrics }: { architecture: Architecture; metrics: MetricDefinition[] }) {
  const [layer, setLayer] = useState<(typeof architecture.layers)[number]["code"]>("operational");
  const metadata = lineage[layer];
  const example = architecture.layers.find((row) => row.code === layer);
  const status = architecture.quality_status === "passed" ? "Passed" : "Review required";
  return (
    <div className={styles.stack}>
      <section id="data-lineage" className={styles.panel} aria-labelledby="lineage-heading">
        <div className={styles.sectionHeader}><div><h2 id="lineage-heading">From source records to reports</h2>
          <p>Architecture overview · Workforce-owned SQLite · Revision {architecture.dataset.revision}</p></div></div>
        <p className={styles.caption}>The shared backend reads a committed snapshot. Reports reflect accepted
          source changes on the next query. Survey publication adds its own evidence and review gate.</p>
        <ol className={styles.lineageFlow} aria-label="Data lineage">
          {Object.values(lineage).map(({ title, purpose }) =>
            <li key={title}><strong>{title}</strong><span>{purpose}</span></li>)}
        </ol>
      </section>
      <section id="data-layers" className={styles.panel} aria-labelledby="layer-heading">
        <div className={styles.sectionHeader}><div><h2 id="layer-heading">Explore the data layers</h2>
          <p>Live synthetic examples at {displayDay(architecture.as_of_date)}.</p></div></div>
        <div className={styles.diagramControls} role="group" aria-label="Data layer">
          {architecture.layers.map(({ code }) => <button key={code} type="button" className={styles.secondaryButton}
            aria-pressed={layer === code} onClick={() => setLayer(code)}>{lineage[code].title}</button>)}
        </div>
        <div className={styles.layerDetails}>
          <dl>
            <div><dt>Purpose</dt><dd>{metadata.purpose}</dd></div>
            <div><dt>Permitted content</dt><dd>{metadata.content}</dd></div>
            <div><dt>Transformation</dt><dd>{metadata.transform}</dd></div>
            <div><dt>Demo owner</dt><dd>{metadata.owner}</dd></div>
            <div><dt>Snapshot quality</dt><dd>{status} · <a href="#quality">See checks</a></dd></div>
          </dl>
          {example ? <div>
            <h3>Example row</h3>
            <p><code>{example.relation}</code></p>
            {Object.keys(example.values).length ? <div className={styles.tableScroll} tabIndex={0} role="region"
              aria-label={`${metadata.title} example row`}>
              <table className={styles.table}>
                <thead><tr><th scope="col">Field</th><th scope="col">Value</th></tr></thead>
                <tbody>{Object.entries(example.values).map(([field, value]) => <tr key={field}>
                  <th scope="row"><code>{field}</code></th>
                  <td>{typeof value === "number" ? displayNumber(value) : value ?? "Null"}</td>
                </tr>)}</tbody>
              </table>
            </div> : <p>No matching row at this date.</p>}
          </div> : null}
        </div>
      </section>
      <DataModel />
      <section id="quality" className={styles.panel} aria-labelledby="quality-heading">
        <div className={styles.sectionHeader}><div><h2 id="quality-heading">Data quality checks</h2>
          <p>Revision {architecture.dataset.revision} · {displayDay(architecture.as_of_date)}</p></div>
          <span className={architecture.quality_status === "passed" ? styles.statusBadge : styles.warningBadge}>
            {status}
          </span>
        </div>
        <p className={styles.caption}>
          Four reconciliation checks compare accepted source rows with Silver. Counts describe
          affected records per rule and may overlap.
        </p>
        <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Data quality rule details">
          <table className={styles.table}>
            <thead><tr><th scope="col">Implemented check</th><th scope="col">Issues</th>
              <th scope="col">Potential metric impact</th><th scope="col">Suggested investigation</th></tr></thead>
            <tbody>{Object.entries(architecture.issues).map(([code, count]) => {
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
          Any nonzero check flags the current snapshot for review. Investigate its lineage before drawing a conclusion.
        </p>
      </section>
      <VoiceProcess />
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
