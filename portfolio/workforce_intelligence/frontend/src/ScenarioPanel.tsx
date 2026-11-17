import { useEffect, useState, type FormEvent } from "react";
import { workforceRequest, WorkforceApiError, workforceWrite } from "./data-api";
import type { PlanningProps } from "./ForecastPanel";
import { displayDay, displayNumber } from "./format";
import { checkPlanningSnapshot, planningPayload, type ScenarioInputs, type ScenarioRun } from "./planning-api";
import styles from "./workforce-scaffold.module.css";

type Field = {
  key: keyof ScenarioInputs; label: string; min?: number; max: number; step?: number; percent?: boolean;
};

const fields: Array<{ label: string; fields: Field[] }> = [
  { label: "Recruitment pipeline", fields: [
    { key: "approvals_per_month", label: "Approved positions per month", max: 500 },
    { key: "applicants_per_position", label: "Applicants per position", max: 100, step: 0.1 },
    { key: "shortlist_rate", label: "Applicants shortlisted (%)", max: 100, step: 0.1, percent: true },
    { key: "interview_rate", label: "Shortlisted candidates interviewed (%)", max: 100, step: 0.1, percent: true },
    { key: "offer_rate", label: "Interviews leading to offers (%)", max: 100, step: 0.1, percent: true },
    { key: "acceptance_rate", label: "Offer acceptance (%)", max: 100, step: 0.1, percent: true },
    { key: "checks_pass_rate", label: "Accepted offers clearing checks (%)", max: 100, step: 0.1, percent: true },
  ] },
  { label: "Time to fill", fields: [
    { key: "days_to_offer", label: "Approval to accepted offer (days)", max: 180 },
    { key: "days_for_checks", label: "Pre-employment checks (days)", max: 180 },
    { key: "days_to_start", label: "Checks to start (days)", max: 180 },
  ] },
  { label: "Workforce movement", fields: [
    { key: "planned_starts", label: "Planned starts from open pipeline (total)", max: 5000 },
    { key: "internal_rate", label: "Internal appointments (%)", max: 100, step: 0.1, percent: true },
    { key: "early_attrition_rate", label: "External starters leaving within 12 months (%)", max: 100, step: 0.1, percent: true },
    { key: "wte_per_position", label: "Average WTE per position", min: 0.1, max: 1, step: 0.05 },
  ] },
];

const valueText = (number: number | null) => number === null ? "Unavailable" : displayNumber(number);

export function ScenarioPanel(props: PlanningProps) {
  return <section id="scenarios" className={styles.panel} aria-labelledby="scenarios-heading">
    <h2 id="scenarios-heading">What-if scenarios</h2>
    <ScenarioControls {...props} />
  </section>;
}

function ScenarioControls({ dataset, cutoff, onError }: PlanningProps) {
  const [baseline, setBaseline] = useState<ScenarioInputs | null>(null);
  const [result, setResult] = useState<ScenarioRun | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void workforceRequest<ScenarioInputs>("scenarios", { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setBaseline(data); })
      .catch((failure: WorkforceApiError) => {
        if (!controller.signal.aborted) { setError(failure.message); onError(failure); }
      });
    return () => controller.abort();
  }, [attempt, onError]);

  if (!baseline) return error ? <p className={styles.notice} role="alert">{error}{" "}
    <button type="button" className={styles.linkButton} onClick={() => {
      setError("");
      setAttempt((value) => value + 1);
    }}>Retry</button></p> : <p className={styles.message} role="status">Loading reference assumptions…</p>;

  async function run(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const inputs = Object.fromEntries(fields.flatMap((group) => group.fields.map(({ key, percent }) =>
      [key, Number(form.get(key)) / (percent ? 100 : 1)])));
    setError("");
    setResult(null);
    setBusy(true);
    try {
      const data = await workforceWrite<ScenarioRun>("scenarios", "POST", {
        ...planningPayload(dataset, cutoff, Number(form.get("horizon"))), inputs,
      });
      checkPlanningSnapshot(dataset, data.dataset);
      setResult(data);
    } catch (failure) {
      if (failure instanceof WorkforceApiError) { setError(failure.message); onError(failure); }
    } finally {
      setBusy(false);
    }
  }

  return <>
    <p className={styles.caption}>
      Change the reference inputs to compare two illustrative paths from the same position on {displayDay(cutoff)}.
    </p>
    <form onSubmit={(event) => void run(event)} onReset={() => { setResult(null); setError(""); }}
      onChange={() => setResult(null)} aria-label="What-if scenario inputs">
      {fields.map((group) => <fieldset key={group.label} disabled={busy} className={styles.planningGroup}>
        <legend>{group.label}</legend>
        <div className={styles.planningFields}>
          {group.fields.map(({ key, label, min = 0, max, step = 1, percent }) =>
            <label key={key}>{label}
              <input name={key} type="number" required min={min} max={max} step={step}
                defaultValue={percent ? Math.round(baseline[key] * 1000) / 10 : baseline[key]} />
            </label>)}
        </div>
      </fieldset>)}
      <div className={styles.filterBar}>
        <label>Scenario horizon<select name="horizon" defaultValue="6" disabled={busy}>
          {[1, 3, 6, 12].map((months) => <option key={months} value={months}>{months} months</option>)}
        </select></label>
        <button className={styles.primaryButton} type="submit" disabled={busy}>Run scenario</button>
        <button className={styles.secondaryButton} type="reset" disabled={busy}>Restore reference inputs</button>
      </div>
    </form>
    {busy ? <p className={styles.message} role="status">Evaluating scenarios…</p> : null}
    {error ? <p className={styles.notice} role="alert">{error}</p> : null}
    {result ? <ScenarioComparison result={result} /> : null}
    <details className={styles.catalogueEntry}>
      <summary>Scenario assumptions and limits</summary>
      <p>The reference starts with the same observed WTE as the edited scenario and uses fixed illustrative
        inputs. Each month adds approved positions. Applications pass through the specified stages,
        capped at one appointment per position. Starts lag approvals in 30-day planning buckets.</p>
      <p>Planned starts are spread over the horizon and capped by the open positions and WTE at the cutoff.
        Internal appointments fill a vacancy without adding workforce WTE. Early attrition reduces
        projected external starter WTE over time. The workforce gap is budget minus substantive WTE.</p>
      <p>Budget and the existing workforce are held constant. The model omits unplanned leavers, backfill,
        cancellations and further activity on the opening pipeline. Time to fill applies to successful
        new positions. Outcomes are conditional on the inputs, with no statistical uncertainty interval.</p>
    </details>
  </>;
}

function ScenarioComparison({ result }: { result: ScenarioRun }) {
  const { evaluation: { opening, inputs, scenario, baseline }, dataset, model_version } = result;
  const lastScenario = scenario.months[scenario.months.length - 1];
  const lastBaseline = baseline.months[baseline.months.length - 1];
  const summary = [
    { label: "Expected starts (total)", scenario: scenario.expected_starts, baseline: baseline.expected_starts },
    { label: "Open vacancy WTE at horizon", scenario: lastScenario.vacancy_wte, baseline: lastBaseline.vacancy_wte },
    { label: "Workforce gap WTE at horizon", scenario: lastScenario.workforce_gap_wte, baseline: lastBaseline.workforce_gap_wte },
    { label: "Time to fill one successful new position (days)", scenario: scenario.expected_time_to_fill,
      baseline: baseline.expected_time_to_fill },
  ];

  return <section aria-labelledby="scenario-comparison">
    <h3 id="scenario-comparison">Scenario comparison</h3>
    <p className={styles.caption} role="status">
      Opening position · {valueText(opening.vacancy_wte)} vacancy WTE · {valueText(opening.substantive_wte)} substantive WTE
      {" "}· {valueText(opening.budgeted_wte)} budget WTE
    </p>
    {scenario.modelled_planned_starts < inputs.planned_starts ?
      <p className={styles.notice}>Opening capacity limits planned starts to {valueText(scenario.modelled_planned_starts)}.</p> : null}
    <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Scenario summary">
      <table className={styles.table}>
        <thead><tr><th scope="col">Outcome</th><th scope="col">Your scenario</th>
          <th scope="col">Reference baseline</th><th scope="col">Change</th></tr></thead>
        <tbody>{summary.map((row) => <tr key={row.label}><th scope="row">{row.label}</th>
          <td>{valueText(row.scenario)}</td><td>{valueText(row.baseline)}</td>
          <td>{valueText(row.scenario === null || row.baseline === null ? null :
            Number((row.scenario - row.baseline).toFixed(3)))}</td></tr>)}</tbody>
      </table>
    </div>
    <details className={styles.catalogueEntry}>
      <summary>Monthly comparison and run details</summary>
      <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Monthly scenario comparison">
        <table className={styles.table}>
          <thead><tr><th scope="col">Month</th><th scope="col">Starts</th>
            <th scope="col">Baseline starts</th><th scope="col">Vacancy WTE</th><th scope="col">Baseline vacancy WTE</th>
            <th scope="col">Gap WTE</th><th scope="col">Baseline gap WTE</th></tr></thead>
          <tbody>{scenario.months.map((month, index) => {
            const other = baseline.months[index];
            return <tr key={month.month}><th scope="row">{month.month}</th>
              <td>{valueText(month.starts)}</td><td>{valueText(other.starts)}</td>
              <td>{valueText(month.vacancy_wte)}</td><td>{valueText(other.vacancy_wte)}</td>
              <td>{valueText(month.workforce_gap_wte)}</td><td>{valueText(other.workforce_gap_wte)}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>
      <p>Dataset {dataset.dataset_generation} · Revision {dataset.revision} · Model {model_version}
        {" "}· Run <code>{result.run_id}</code></p>
    </details>
  </section>;
}
