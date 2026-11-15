import type { WorkforceTrendReport, WorkforceTrendPoint } from "./data-api";
import { displayNumber, displayWindow } from "./format";
import styles from "./workforce-scaffold.module.css";

const plot = { left: 35, right: 740, top: 14, bottom: 183 };

/** One point-in-time WTE snapshot per month; counts are period events. */
export function WorkforceTrend({ trend }: { trend: WorkforceTrendReport }) {
  const { points, window } = trend.trend;
  const ceiling = Math.max(1, ...points.flatMap((point) => [
    point.substantive_wte, point.budgeted_wte ?? 0,
  ]));
  const x = (index: number) => plot.left + (plot.right - plot.left) *
    (points.length > 1 ? index / (points.length - 1) : 0.5);
  const y = (value: number) => plot.bottom - value / ceiling * (plot.bottom - plot.top);
  const path = (getValue: (point: WorkforceTrendPoint) => number | null) => {
    let continued = false;
    return points.map((point, index) => {
      const value = getValue(point);
      if (value === null) { continued = false; return ""; }
      const command = continued ? "L" : "M";
      continued = true;
      return `${command}${x(index).toFixed(2)} ${y(value).toFixed(2)}`;
    }).filter(Boolean).join(" ");
  };

  return (
    <section id="workforce-trend" className={styles.panel} aria-labelledby="workforce-trend-heading">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="workforce-trend-heading">Workforce trend</h2>
          <p>Budgeted and substantive WTE snapshots · {displayWindow(window)}</p>
        </div>
      </div>
      <p className={styles.trendLegend}>
        <span><span className={styles.trendBudgetKey} aria-hidden="true" /> Budgeted WTE</span>
        <span><span className={styles.trendStaffKey} aria-hidden="true" /> Substantive WTE</span>
      </p>
      {points.length ? (
        <>
          <svg className={styles.trendChart} viewBox="0 0 760 213" role="img"
            aria-label="Historical budgeted and substantive WTE by reporting month">
            {[0, 0.5, 1].map((fraction) => {
              const guideY = y(ceiling * fraction);
              return <g key={fraction}>
                <line x1={plot.left} x2={plot.right} y1={guideY} y2={guideY}
                  stroke="var(--wi-border)" strokeWidth="1" />
                <text x="29" y={guideY + 4} textAnchor="end" fontSize="11"
                  fill="var(--wi-muted)">{displayNumber(ceiling * fraction)}</text>
              </g>;
            })}
            <path d={path((point) => point.budgeted_wte)} fill="none"
              stroke="var(--wi-warning)" strokeWidth="2.5" strokeLinejoin="round" />
            <path d={path((point) => point.substantive_wte)} fill="none"
              stroke="var(--wi-accent)" strokeWidth="2.5" strokeLinejoin="round" />
            <text x={plot.left} y="205" fontSize="12" fill="var(--wi-muted)">
              {points[0].month_key}
            </text>
            <text x={plot.right} y="205" textAnchor="end" fontSize="12" fill="var(--wi-muted)">
              {points[points.length - 1].month_key}
            </text>
          </svg>
          <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Monthly Workforce trend table">
            <table className={styles.table}>
              <thead><tr>
                <th scope="col">Month</th><th scope="col">As of</th><th scope="col">Budget WTE</th>
                <th scope="col">Substantive WTE</th><th scope="col">Gap WTE</th>
                <th scope="col">Starters</th><th scope="col">Leavers</th>
              </tr></thead>
              <tbody>{points.slice(-12).reverse().map((point) => (
                <tr key={point.month_key}>
                  <th scope="row">{point.month_key}{point.partial_period ? " (partial)" : ""}</th>
                  <td>{point.as_of_date}</td>
                  <td>{point.budgeted_wte === null ? "Not available" : displayNumber(point.budgeted_wte)}</td>
                  <td>{displayNumber(point.substantive_wte)}</td>
                  <td>{point.workforce_gap_wte === null ? "Not available" : displayNumber(point.workforce_gap_wte)}</td>
                  <td>{point.new_starters}</td><td>{point.leavers}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <p className={styles.caption}>
            Chart covers all {points.length} observed months; table shows the latest 12.
            WTE is a snapshot at the listed date; starters and leavers are events within each
            selected calendar-month interval. Partial intervals are labelled. Synthetic data only.
          </p>
        </>
      ) : <p className={styles.message}>No historical observations in this reporting period.</p>}
    </section>
  );
}
