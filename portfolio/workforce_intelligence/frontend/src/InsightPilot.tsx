import { useState } from "react";
import { sameGeneration, vacancyRateInsight, WorkforceApiError, type Dataset, type Insight, type Window } from "./data-api";
import { displayNumber, displayObservation, displayWindow } from "./format";
import styles from "./workforce-scaffold.module.css";

export function InsightPilot({ window, dataset, onAccessError }: {
  window: Window; dataset: Dataset; onAccessError: (error: WorkforceApiError) => void;
}) {
  const [answer, setAnswer] = useState<Insight | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function ask() {
    setBusy(true);
    setAnswer(null);
    setError("");
    try {
      const result = await vacancyRateInsight(window);
      if (sameGeneration(dataset, result.dataset) && result.dataset.revision === dataset.revision) setAnswer(result);
      else setError("The dataset changed. Refresh the dashboard before asking again.");
    } catch (failure) {
      if (failure instanceof WorkforceApiError && [401, 403, 404].includes(failure.status)) onAccessError(failure);
      else setError("The answer is unavailable. Check the reporting dates and try again.");
    } finally { setBusy(false); }
  }

  const current = answer?.metric.current;
  return (
    <section id="insight-pilot" className={styles.panel} aria-labelledby="pilot-heading">
      <div className={styles.sectionHeader}><div><h2 id="pilot-heading">Insight Pilot</h2>
        <p>Uses the governed metrics for this reporting period.</p></div></div>
      <button type="button" onClick={() => void ask()} disabled={busy} className={`${styles.secondaryButton} ${styles.pilotButton}`}>
        {busy ? "Checking the data…" : "Explain the vacancy rate"}
      </button>
      {error ? <p className={styles.errorText} role="alert">{error}</p> : null}
      {answer && current ? <div className={styles.pilotAnswer} role="status">
        <p><strong>{displayObservation(current, "%")}</strong> · {displayWindow(answer.window)}</p>
        <p>{answer.metric.definition.formula}</p>
        {current.reason ? <p>{current.reason}</p> : null}
        {current.numerator !== null && current.denominator !== null ? <p>
          {displayNumber(current.numerator)} open vacancy WTE ÷ {displayNumber(current.denominator)} budgeted WTE × 100
        </p> : null}
        <p>{answer.quality_status === "passed" ? "Data checks passed." : "Review the data-quality checks before interpreting this result."} {answer.limitation}</p>
        <a href={`#${answer.report_section}`}>Return to Recruitment overview</a>
      </div> : null}
    </section>
  );
}
