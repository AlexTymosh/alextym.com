import { useEffect, useState } from "react";
import { workforceRequest, WorkforceApiError, workforceWrite, type Dataset } from "./data-api";
import { displayDay, displayNumber } from "./format";
import { ForecastChart } from "./ForecastChart";
import { checkPlanningSnapshot, FORECAST_METRICS, planningPayload, type ForecastHistory,
  type ForecastMetric, type ForecastRun } from "./planning-api";
import styles from "./workforce-scaffold.module.css";

export type PlanningProps = { dataset: Dataset; cutoff: string; onError: (failure: WorkforceApiError) => void };

export function ForecastPanel(props: PlanningProps) {
  return <section id="forecast" className={styles.panel} aria-labelledby="forecast-heading">
    <h2 id="forecast-heading">Forecasting</h2>
    <ForecastControls {...props} />
  </section>;
}

function ForecastControls({ dataset, cutoff, onError }: PlanningProps) {
  const [metric, setMetric] = useState<ForecastMetric>("vacancy_wte");
  const [horizon, setHorizon] = useState(6);
  const [enabled, setEnabled] = useState(false);
  const [actual, setActual] = useState<{ metric: ForecastMetric; data: ForecastHistory } | null>(null);
  const [result, setResult] = useState<{ key: string; run: ForecastRun } | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const selectedMetric = FORECAST_METRICS[metric];
  const runKey = `${metric}:${horizon}:${attempt}`;
  const run = enabled && result?.key === runKey ? result.run : null;
  const chartHistory = run?.forecast.history ?? (actual?.metric === metric ? actual.data.history : null);
  const fault = failure?.key === `${metric}:${attempt}` || (enabled && failure?.key === runKey) ? failure : null;
  const waiting = !fault && (enabled ? !run : !chartHistory);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ metric, as_of_date: cutoff });
    void workforceRequest<ForecastHistory>(`forecast/history?${query}`, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        checkPlanningSnapshot(dataset, data.dataset);
        setActual({ metric, data });
      }).catch((error: WorkforceApiError) => {
        if (!controller.signal.aborted) {
          setFailure({ key: `${metric}:${attempt}`, message: error.message });
          onError(error);
        }
      });
    return () => controller.abort();
  }, [dataset, cutoff, metric, attempt, onError]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    void workforceWrite<ForecastRun>("forecast", "POST", { ...planningPayload(dataset, cutoff, horizon), metric },
      controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      checkPlanningSnapshot(dataset, data.dataset);
      setResult({ key: runKey, run: data });
    }).catch((error: WorkforceApiError) => {
      if (!controller.signal.aborted) {
        setFailure({ key: runKey, message: error.message });
        onError(error);
      }
    });
    return () => controller.abort();
  }, [enabled, dataset, cutoff, horizon, metric, runKey, onError]);

  const forecast = run?.forecast;
  return <>
    <p className={styles.caption}>Complete months through {displayDay(cutoff)} · Illustrative synthetic data</p>
    <div className={styles.filterBar}>
      <label>Forecast metric<select value={metric}
        onChange={(event) => { setFailure(null); setMetric(event.currentTarget.value as ForecastMetric); }}>
        {Object.entries(FORECAST_METRICS).map(([code, definition]) => <option key={code} value={code}>
          {definition.label}</option>)}
      </select></label>
      <label>Forecast horizon<select value={horizon} onChange={(event) => {
        setFailure(null);
        setHorizon(Number(event.currentTarget.value));
      }}>
        {[1, 3, 6, 12].map((months) => <option key={months} value={months}>{months} months</option>)}
      </select></label>
      <label className={styles.planningToggle}>
        <input type="checkbox" checked={enabled} onChange={(event) => {
          setFailure(null);
          setEnabled(event.currentTarget.checked);
        }} /> Enable forecast
      </label>
    </div>
    {waiting ? <p className={styles.message} role="status">{enabled ? "Comparing forecast models…" : "Loading monthly actuals…"}</p> : null}
    {fault ? <div className={styles.notice} role="alert">{fault.message}{" "}
      <button type="button" className={styles.linkButton} onClick={() => {
        setFailure(null);
        setAttempt((value) => value + 1);
      }}>Retry</button></div> : null}
    {forecast?.status === "insufficient_history" ? <p className={styles.notice} role="status">
      Insufficient history. {forecast.training_months} consecutive usable months are available.
      Compare models with at least {forecast.minimum_months} complete months.
      {dataset.scenario_code === "interview-core" ? " Select Load full dataset in the header to demonstrate a forecast." : ""}
    </p> : null}
    {chartHistory ? <ForecastChart history={chartHistory} future={forecast?.projected ?? []}
      metric={selectedMetric.label} unit={selectedMetric.unit}
      showBaseline={forecast?.selected === "Simple exponential smoothing"} /> : null}
    {forecast?.selected ? <div className={styles.notice} role="status">
      <strong>{forecast.selected}</strong> · Training {forecast.training_start} to {forecast.training_end}
      {" "}({forecast.training_months} months) · {forecast.horizon}-month horizon
      <br />One-month-ahead mean absolute error over {forecast.validation_months} rolling validation months
      {forecast.scores.map(({ model, mae }) => <div key={model}>
        {model} · {displayNumber(mae)} {selectedMetric.unit === "%" ? "percentage points" : selectedMetric.unit}
      </div>)}
    </div> : null}
    <details className={styles.catalogueEntry}>
      <summary>Forecast assumptions and limits</summary>
      <p>{selectedMetric.method}</p>
      <p>Seasonal naïve repeats the last observed year. Simple exponential smoothing uses a fixed
        0.35 smoothing factor. The lower rolling validation error wins, with ties going to the baseline.
        Missing observations break the training series. The first forecast is the next full calendar month.</p>
      <p>The validation measures one-month-ahead error. This demo supplies point estimates and no calibrated
        prediction bands. Treat longer horizons and changes in the underlying workforce as uncertain.</p>
    </details>
  </>;
}
