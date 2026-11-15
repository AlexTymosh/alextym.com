import type { FormEvent, ReactNode } from "react";
import type { Comparison, Dashboard, Dataset, Filters, Window } from "./data-api";
import { displayCode, displayNumber, displayObservation, displayWindow } from "./format";
import { InclusiveRecruitment } from "./InclusiveRecruitment";
import { RecruitmentChannels } from "./RecruitmentChannels";
import { WorkforceTrend } from "./WorkforceTrend";
import { VacancyAgeing } from "./VacancyAgeing";
import styles from "./workforce-scaffold.module.css";

const METRIC_ORDER = [
  "workforce_gap_wte", "open_vacancies", "median_time_to_hire", "vacancy_rate", "vacancy_wte",
  "new_starters", "budgeted_wte", "substantive_wte", "offer_acceptance_rate",
];
const OUTCOME_GROUPS = [
  {
    label: "Recruitment and onboarding",
    description: "Accepted offers, internal appointments and completed probation decisions.",
    codes: ["offer_to_start_conversion", "internal_appointment_rate", "probation_pass_rate"],
  },
  {
    label: "Retention and leavers",
    description: "Opening-cohort retention, completed 365-day starter follow-up and dated leavers.",
    codes: ["retention_rate", "early_attrition_12m", "new_leavers"],
  },
  {
    label: "Progression and development",
    description: "Recorded progression, PDR and learning events; not population-wide compliance.",
    codes: ["internal_progressions", "pdr_completion_rate", "learning_completion_rate"],
  },
] as const;

const STAGE_LABELS: Record<string, string> = {
  received: "Application received", screened: "Eligibility screened", shortlisted: "Shortlisted",
  interviewed: "Interviewed", conditional_offer: "Conditional offer", offer_accepted: "Offer accepted",
  checks_completed: "Checks completed", start_confirmed: "Start confirmed", started: "Started",
  probation_completed: "Probation completed",
};
const DIRECTION = { up: "↑ Up", down: "↓ Down", flat: "No change", unavailable: "Comparison unavailable" };

type Props = {
  dashboard: Dashboard;
  filters: Filters;
  onFilters: (filters: Filters) => void;
  pilot?: ReactNode;
};

export function ExecutiveDashboard({ dashboard, filters, onFilters, pilot }: Props) {
  const { executive, quality_status: quality, dataset } = dashboard.executive;
  const currentWindow = executive.current_window;
  const metrics = new Map(executive.metrics.map((metric) => [metric.definition.code, metric]));
  const { vacancies, funnel } = dashboard;
  const applicationCount = funnel.funnel.stages[0]?.application_count ?? 0;
  const applyDates = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = new FormData(event.currentTarget);
    onFilters({ ...filters, start: String(input.get("from")), end: String(input.get("through")) });
  };

  return (
    <div className={styles.stack}>
      <section id="executive" aria-labelledby="executive-heading">
        <div className={styles.sectionHeader}>
          <div><h2 id="executive-heading">Recruitment overview</h2><p>{displayWindow(currentWindow)}</p></div>
          <span className={quality === "passed" ? styles.statusBadge : styles.warningBadge}>
            {quality === "passed" ? "Data checks passed" : "Review data quality"}
          </span>
        </div>
        <form aria-label="Reporting period" className={styles.filterBar} onSubmit={applyDates}
          key={`${currentWindow.start}:${currentWindow.end}`}>
          <label>Period start<input name="from" type="date" defaultValue={currentWindow.start}
            min={dataset.history_start} max={dataset.as_of_date} required /></label>
          <label>As of date<input name="through" type="date" defaultValue={currentWindow.end}
            min={dataset.history_start} max={dataset.as_of_date} required /></label>
          <button type="submit" className={styles.secondaryButton}>Apply dates</button>
        </form>
        <div className={styles.metricGrid}>
          {METRIC_ORDER.map((code, index) => {
            const metric = metrics.get(code);
            return metric ? <MetricCard key={code} metric={metric} dataset={dataset}
              window={currentWindow} previousWindow={executive.previous_window} highlight={index < 3}
              quality={quality} supplementary={code === "workforce_gap_wte" ? [
                metrics.get("budgeted_wte"), metrics.get("substantive_wte"),
              ] : undefined} /> : null;
          })}
        </div>
      </section>

      <WorkforceTrend trend={dashboard.trend} />

      <VacancyAgeing ageing={dashboard.ageing} onSelectVacancy={(id) => {
        onFilters({ ...filters, vacancyId: id });
        document.getElementById("funnel")?.scrollIntoView({ block: "start" });
      }} />

      <section id="vacancies" className={styles.panel} aria-labelledby="vacancy-heading">
        <div className={styles.sectionHeader}>
          <div><h2 id="vacancy-heading">Vacancy lifecycle</h2><p>Requests and filled positions at the selected date.</p></div>
        </div>
        {vacancies.items.length ? (
          <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Vacancy lifecycle table">
            <table className={styles.table}>
              <thead><tr><th scope="col">Vacancy</th><th scope="col">Status</th><th scope="col">Filled positions</th>
                <th scope="col">Filled WTE</th><th scope="col">Open WTE</th></tr></thead>
              <tbody>{vacancies.items.map((vacancy) => (
                <tr key={vacancy.id}>
                  <th scope="row">{vacancy.title}</th><td>{displayCode(vacancy.status)}</td>
                  <td>{vacancy.filled_positions} of {vacancy.approved_positions}</td>
                  <td>{displayNumber(vacancy.filled_wte)}</td><td>{displayNumber(vacancy.open_wte)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className={styles.message}>There are no vacancy records for this reporting date.</p>}
      </section>

      <section id="funnel" className={styles.panel} aria-labelledby="funnel-heading">
        <div className={styles.sectionHeader}>
          <div><h2 id="funnel-heading">Candidate funnel</h2><p>Distinct applications received in the selected period.</p></div>
          <label className={styles.control}>Vacancy
            <select value={filters.vacancyId} onChange={(event) => onFilters({ ...filters, vacancyId: event.target.value })}>
              <option value="">All vacancies</option>
              {filters.vacancyId && !vacancies.items.some((item) => item.id === filters.vacancyId) &&
                <option value={filters.vacancyId}>Selected: {filters.vacancyId}</option>}
              {vacancies.items.map((vacancy) => <option key={vacancy.id} value={vacancy.id}>{vacancy.title}</option>)}
            </select>
          </label>
        </div>
        {applicationCount ? (
          <>
            <p className={styles.funnelRate}>Application-to-start conversion <strong>
              {displayObservation(funnel.funnel.application_to_start, "%")}
            </strong></p>
            <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Application stage table">
              <table className={styles.table}>
                <thead><tr><th scope="col">Stage</th><th scope="col">Applications</th>
                  <th scope="col">From prior stage</th><th scope="col">Median days</th></tr></thead>
                <tbody>{funnel.funnel.stages.map((stage) => (
                  <tr key={stage.stage}>
                    <th scope="row">{STAGE_LABELS[stage.stage] ?? displayCode(stage.stage)}</th>
                    <td><div className={styles.barCell}><span>{stage.application_count}</span>
                      <span aria-hidden="true" className={styles.barTrack}><span style={{
                        width: `${stage.application_count / applicationCount * 100}%`,
                      }} /></span></div></td>
                    <td>{stage.conversion_from_previous ? displayObservation(stage.conversion_from_previous, "%") : "—"}</td>
                    <td>{stage.median_days_from_previous ? displayObservation(stage.median_days_from_previous) : "—"}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <p className={styles.caption}>Stage rates reflect progress by the cutoff. Recent applications have had less time to advance.</p>
          </>
        ) : <p className={styles.message}>There are no applications in this cohort.</p>}
      </section>
      <RecruitmentChannels sources={dashboard.sources} vacancyFiltered={Boolean(filters.vacancyId)} />
      <InclusiveRecruitment inclusive={dashboard.inclusive} />
      <section id="outcomes" className={styles.panel} aria-labelledby="outcomes-heading">
        <div className={styles.sectionHeader}>
          <div>
            <h2 id="outcomes-heading">Workforce outcomes</h2>
            <p>Governed workforce measures for {displayWindow(currentWindow)}.</p>
          </div>
        </div>
        <div className={styles.stack}>
          {OUTCOME_GROUPS.map((group) => (
            <div key={group.label}>
              <p className={styles.caption}><strong>{group.label}</strong> · {group.description}</p>
              <div className={styles.metricGrid}>
                {group.codes.map((code) => {
                  const metric = metrics.get(code);
                  return metric ? (
                    <MetricCard key={code} metric={metric} dataset={dataset}
                      window={currentWindow} previousWindow={executive.previous_window}
                      highlight={false} quality={quality} />
                  ) : null;
                })}
              </div>
            </div>
          ))}
        </div>
        <p className={styles.caption}>
          These are synthetic measures. Missing follow-up or a zero eligible denominator is
          shown as Not available, never as a zero outcome. Definitions explain cohort scope.
        </p>
      </section>
      {pilot}
    </div>
  );
}

function MetricCard({ metric, window, previousWindow, dataset, highlight, quality, supplementary }: {
  metric: Comparison; window: Window; previousWindow: Window | null; dataset: Dataset; highlight: boolean;
  quality: string; supplementary?: Array<Comparison | undefined>;
}) {
  const { definition, current, previous, direction } = metric;
  const unit = definition.unit === "people" || definition.unit === "vacancies" ? "" : definition.unit;
  const isAvailable = current.status === "available";
  const value = displayObservation(current, unit);
  const parts = isAvailable ? [
    current.numerator !== null && definition.denominator ? `${definition.numerator} ${displayNumber(current.numerator)}` : "",
    current.denominator !== null ? `${definition.denominator} ${displayNumber(current.denominator)}` : "",
    current.sample_size !== null ? `${current.sample_size} completed observation(s)` : "",
  ].filter(Boolean) : [];
  return (
    <article className={`${styles.metric} ${highlight ? styles.metricHighlight : ""}`} aria-label={definition.name}>
      <h3>{definition.name}</h3>
      <p className={styles.metricValue} data-metric={definition.code}>{value}</p>
      <p className={styles.metricComparison}>{previousWindow ?
        <><span>{DIRECTION[direction]}</span> <span>· Prior {displayObservation(previous, unit)}</span></> :
        "No comparable period"}</p>
      <details className={styles.metricDetails}>
        <summary title={definition.formula} aria-label={`Definition of ${definition.name}`}>Definition</summary>
        <div>
          <p><strong>{definition.formula}</strong></p>
          {current.reason && <p>{current.reason}</p>}
          {parts.map((part) => <p key={part}>{part}</p>)}
          {supplementary?.map((item) => item && <p key={item.definition.code}>
            {item.definition.name} {displayObservation(item.current, item.definition.unit)}
          </p>)}
          <p>{definition.caveat}</p>
          <p>Excluded · {definition.exclusions}</p>
          <p>{displayWindow(window)} · Definition v{definition.version} · Revision {dataset.revision}</p>
          <p>{quality === "passed" ? "Data checks passed" : "Review data quality"} · Synthetic data</p>
        </div>
      </details>
    </article>
  );
}
