import { displayNumber } from "./format";
import type { ActualMonth, ProjectedMonth } from "./planning-api";
import styles from "./workforce-scaffold.module.css";

const plot = { left: 58, right: 736, top: 34, bottom: 198 };

function monthNumber(month: string) {
  const [year, number] = month.split("-").map(Number);
  return year * 12 + number;
}

export function ForecastChart({ history, future, metric, unit, showBaseline }: {
  history: ActualMonth[]; future: ProjectedMonth[]; metric: string; unit: string; showBaseline: boolean;
}) {
  const firstMonth = history[0]?.month;
  const lastMonth = future.at(-1)?.month ?? history.at(-1)?.month;
  const observed = history.flatMap(({ value }) => value === null ? [] : [value]);
  if (!firstMonth || !lastMonth || !observed.length) {
    return <p className={styles.message}>No eligible actuals in complete months at this cutoff.</p>;
  }

  const extent = [...observed, ...future.flatMap((point) => [point.value, point.baseline])];
  const min = Math.min(...extent);
  const max = Math.max(...extent);
  const pad = max === min ? Math.max(0.5, Math.abs(max) * 0.05) : (max - min) * 0.12;
  const low = min >= 0 ? Math.max(0, min - pad) : min - pad;
  const high = max + pad;
  const origin = monthNumber(firstMonth);
  const span = Math.max(1, monthNumber(lastMonth) - origin);
  const x = (month: string) => plot.left + (monthNumber(month) - origin) * (plot.right - plot.left) / span;
  const y = (value: number) => plot.bottom - (value - low) * (plot.bottom - plot.top) / (high - low);
  const path = (points: ActualMonth[]) => {
    let previous = false;
    return points.map(({ month, value }) => {
      if (value === null) { previous = false; return ""; }
      const command = previous ? "L" : "M";
      previous = true;
      return `${command}${x(month)} ${y(value)}`;
    }).join(" ");
  };
  const latest = history.at(-1)!;
  const boundary = future[0] ? (x(latest.month) + x(future[0].month)) / 2 : null;
  const series = future.length ? [latest, ...future] : [];
  const baseline = [latest, ...future.map((point) => ({ month: point.month, value: point.baseline }))];
  const chartLabel = future[0] ?
    `${metric} in ${unit}. Actuals through ${latest.month}. Forecast starts ${future[0].month}.` :
    `${metric} in ${unit}. Monthly actuals from ${firstMonth} through ${latest.month}.`;

  return <>
    <div className={styles.tableScroll} role="region" tabIndex={0} aria-label="Forecast chart">
      <svg className={styles.forecastChart} viewBox="0 0 760 228" role="img" aria-label={chartLabel}>
        {boundary !== null ? <rect x={boundary} y={plot.top} width={plot.right - boundary}
          height={plot.bottom - plot.top} fill="var(--wi-accent-soft)" /> : null}
        {[low, (low + high) / 2, high].map((value) => <g key={value}>
          <line x1={plot.left} x2={plot.right} y1={y(value)} y2={y(value)} stroke="var(--wi-border)" />
          <text x={plot.left - 7} y={y(value) + 4} textAnchor="end"
            fill="var(--wi-muted)" fontSize="11">{displayNumber(Number(value.toFixed(1)))}</text>
        </g>)}
        {boundary !== null ? <g>
          <line x1={boundary} x2={boundary} y1={plot.top - 4} y2={plot.bottom} stroke="var(--wi-muted)" />
          <text x={Math.min(boundary + 5, plot.right - 113)} y="22" fill="var(--wi-ink)" fontSize="13">
            Forecast start
          </text>
        </g> : null}
        <path d={path(history)} fill="none" stroke="var(--wi-accent)" strokeWidth="2.5" />
        {history.map(({ month, value }) => value === null ? null :
          <circle key={month} cx={x(month)} cy={y(value)} r="2.4" fill="var(--wi-accent)" />)}
        {future.length ? <path d={path(series)} fill="none"
          stroke="var(--wi-accent)" strokeWidth="2.5" strokeDasharray="7 5" /> : null}
        {showBaseline && future.length ? <path d={path(baseline)} fill="none"
          stroke="var(--wi-warning)" strokeWidth="2" strokeDasharray="2 4" /> : null}
        <text x={plot.left} y="220" fill="var(--wi-muted)" fontSize="12">{firstMonth}</text>
        {lastMonth !== firstMonth ? <text x={plot.right} y="220" textAnchor="end"
          fill="var(--wi-muted)" fontSize="12">{lastMonth}</text> : null}
      </svg>
    </div>
    <p className={styles.trendLegend}>
      <span className={styles.forecastActual}>Actuals</span>
      {future.length ? <span className={styles.forecastProjected}>Selected forecast</span> : null}
      {showBaseline && future.length ? <span className={styles.forecastBaseline}>Seasonal naïve baseline</span> : null}
    </p>
    <details className={styles.catalogueEntry}>
      <summary>Monthly values</summary>
      <div className={styles.tableScroll} role="region" tabIndex={0} aria-label="Monthly forecast data">
        <table className={styles.table}>
          <thead><tr><th scope="col">Month</th><th scope="col">Period</th>
            <th scope="col">{metric} ({unit})</th>
            {future.length ? <th scope="col">Seasonal naïve</th> : null}</tr></thead>
          <tbody>
            {history.map(({ month, value }) => <tr key={month}><th scope="row">{month}</th>
              <td>Actual</td><td>{value === null ? "Unavailable" : displayNumber(value)}</td>
              {future.length ? <td>—</td> : null}</tr>)}
            {future.map(({ month, value, baseline }) => <tr key={month}><th scope="row">{month}</th>
              <td>Forecast</td><td>{displayNumber(value)}</td><td>{displayNumber(baseline)}</td></tr>)}
          </tbody>
        </table>
      </div>
    </details>
  </>;
}
