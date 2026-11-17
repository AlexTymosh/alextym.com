import { useState } from "react";
import styles from "./workforce-scaffold.module.css";

const subjectAreas = [
  {
    label: "Workforce",
    fact: "fact_employment_interval",
    grain: "One intersected substantive contract and assignment for an employee and effective period.",
    joins: [
      ["dim_employee", "employee_id → id", "Synthetic employee key"],
      ["dim_date", "valid_from ≤ date_key < valid_to", "Snapshot date with open-ended intervals"],
      ["dim_organisation", "organisation_id → id", "Organisational unit"],
      ["dim_location", "location_id → id", "Assigned location"],
      ["dim_role", "role_id → id", "Assigned role"],
      ["dim_pay_band", "pay_band → id", "Role pay band"],
    ],
  },
  {
    label: "Recruitment",
    fact: "fact_application",
    grain: "One eligible application linked to a vacancy. Stage events, offers and actual starts retain their own grain.",
    joins: [
      ["dim_date", "received_on → date_key", "Received date"],
      ["dim_campaign", "campaign_id → id", "Vacancy campaign"],
      ["dim_recruitment_source", "source_code → id", "Declared source"],
      ["dim_organisation", "organisation_id → id", "Vacancy organisational unit"],
      ["dim_location", "location_id → id", "Vacancy location"],
      ["dim_role", "role_id → id", "Vacancy role"],
    ],
  },
  {
    label: "People Voice",
    fact: "gold_voice_published_findings",
    grain: "One approved and separately published campaign finding admitted by the Gold review and evidence checks.",
    joins: [
      ["voice_analysis_runs", "analysis_id → id", "Ready run"],
      ["survey_campaigns", "survey_id → id", "Campaign via the analysis"],
      ["voice_evidence_spans", "id → signal_id", "Validated response IDs"],
      ["voice_review_events", "id → signal_id", "Review and publish decisions"],
      ["management_actions", "id → signal_id", "Management follow-up"],
    ],
  },
  {
    label: "Forecasts",
    fact: "fact_forecast",
    grain: "One projected metric month per saved forecasting run, including its seasonal baseline.",
    joins: [
      ["forecast_runs", "run_id → id", "Model, inputs and source revision"],
      ["month_key", "YYYY-MM", "First full future month through the selected horizon"],
    ],
  },
];

export function DataModel() {
  const [selected, setSelected] = useState(0);
  const { label, fact, grain, joins } = subjectAreas[selected];
  return <section id="data-model" className={styles.panel} aria-labelledby="model-heading">
    <div className={styles.sectionHeader}><div>
      <h2 id="model-heading">Data model</h2>
      <p>Fact grain and join paths in Workforce SQLite.</p>
    </div></div>
    <div className={styles.diagramControls} role="group" aria-label="Data model subject">
      {subjectAreas.map((area, index) => <button key={area.label} type="button"
        className={styles.secondaryButton} aria-pressed={selected === index} onClick={() => setSelected(index)}>
        {area.label}</button>)}
    </div>
    <figure className={styles.modelMap} aria-label={`${label} relationship diagram`}>
      <figcaption className={styles.centralFact}>
        <span>Fact grain</span><strong><code>{fact}</code></strong><p>{grain}</p>
      </figcaption>
      <ul className={styles.relations}>
        {joins.map(([relation, keys, purpose]) => <li key={relation}>
          <strong><code>{relation}</code></strong><code>{keys}</code><p>{purpose}</p>
        </li>)}
      </ul>
    </figure>
  </section>;
}
