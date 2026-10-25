"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./dashboard.module.css";

type TrendPoint = { date: string; fleet_count: number; vor: number; non_vor_proxy: number; required: number };
type Case = { registration: string; reason: string; status: string; opened_at: string; garage: string; days: number | null };
type DashboardData = {
  as_of: string; start: string; end: string; required: number | null; scope_warning: string | null;
  vehicle_count: number; operational: number; vor: number; deviation: number | null;
  counts_by_reason: { reason: string; count: number }[];
  case_duration: { mean: number | null; median: number | null; p90: number | null; retained: number; excluded: number };
  case_duration_basis: string; open_cases: number;
  workshops: { garage: string; cases: number; median: number | null; mean: number | null; p90: number | null }[];
  trend: TrendPoint[]; trend_note: string; actions_open: number; overdue: number; blockers: number;
  cases: Case[]; available_garages: string[]; available_reasons: string[]; available_models: string[];
  daily_reporting_warning: string; outlier_method: string;
};
const fmt = (value: number | null, suffix = "") => value == null ? "—" : `${value}${suffix}`;
const percent = (a: number, b: number) => b > 0 ? Math.round(a / b * 1000) / 10 : 0;

function TrendChart({ points, description }: { points: TrendPoint[]; description: string }) {
  const rows = points.slice(-30);
  const max = Math.max(1, ...rows.map(p => Math.max(p.vor, p.non_vor_proxy)));
  const w = 820, h = 245, x0 = 44, x1 = w - 18, y0 = 17, y1 = h - 38;
  const toY = (n: number) => y1 - (n / max) * (y1 - y0);
  const toX = (i: number) => x0 + (i / Math.max(1, rows.length - 1)) * (x1 - x0);
  const path = (key: "vor" | "non_vor_proxy") => rows.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p[key]).toFixed(1)}`).join(" ");
  const ticks = Array.from({ length: 5 }, (_, i) => Math.round(max * i / 4));
  return <section className={styles.chartCard} aria-label="VOR trend chart">
    <div className={styles.cardHeading}><h3>VOR trend · last 30 days</h3><div className={styles.chartLegend}><span><i className={styles.legendRed}/> VOR vehicles</span><span><i className={styles.legendGreen}/> Non-VOR proxy</span></div></div>
    {rows.length ? <svg viewBox={`0 0 ${w} ${h}`} className={styles.lineGraph} role="img" aria-label="Historic VOR vehicle count and calculated non-VOR proxy">
      {ticks.map((t, i) => <g key={i}><line x1={x0} y1={toY(t)} x2={x1} y2={toY(t)} stroke="#e8eef1"/><text x={x0 - 8} y={toY(t) + 4} textAnchor="end" fill="#8293a0" fontSize="11">{t}</text></g>)}
      <path d={path("non_vor_proxy")} fill="none" stroke="#55aa78" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d={path("vor")} fill="none" stroke="#f27678" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
      {rows.map((p, i) => <g key={p.date}><circle cx={toX(i)} cy={toY(p.vor)} r="3" fill="#ee666b"><title>{p.date}: {p.vor} VOR</title></circle><circle cx={toX(i)} cy={toY(p.non_vor_proxy)} r="2.5" fill="#53a875"><title>{p.date}: {p.non_vor_proxy} non-VOR proxy</title></circle></g>)}
      {[0, Math.floor((rows.length - 1) / 2), rows.length - 1].filter((v, i, a) => a.indexOf(v) === i).map(i => <text key={i} x={toX(i)} y={h - 9} textAnchor={i === 0 ? "start" : i === rows.length - 1 ? "end" : "middle"} fill="#83929e" fontSize="11">{rows[i].date}</text>)}
    </svg> : <div className={styles.emptyChart}>No historical reference data for this period.</div>}
    <p className={styles.dataNote}>{description} Non-VOR is a historical proxy, not confirmed on-road deployment.</p>
  </section>;
}

function AvailabilityChart({ data }: { data: DashboardData }) {
  const total = data.vehicle_count;
  const operational = Math.max(0, data.operational);
  const vor = Math.max(0, data.vor);
  const other = Math.max(0, total - operational - vor);
  const opPct = percent(operational, total), vorPct = percent(vor, total);
  const bg = total > 0 ? `conic-gradient(#55aa78 0 ${opPct}%, #f16d72 ${opPct}% ${opPct + vorPct}%, #c8d5df ${opPct + vorPct}% 100%)` : "#e6edf2";
  return <section className={styles.chartCard} aria-label="Fleet availability chart">
    <div className={styles.cardHeading}><h3>Fleet availability</h3><span className={styles.cardNote}>Recorded status · today</span></div>
    <div className={styles.donutLayout}>
      <div className={styles.donut} style={{ background: bg }} role="img" aria-label={`${operational} operational, ${vor} VOR, ${other} other`}><div className={styles.donutHole}><strong>{opPct}%</strong><span>operational</span></div></div>
      <div className={styles.donutLegend}>
        <div><i className={styles.greenDot}/><span>Operational</span><strong>{operational}</strong><small>{opPct}%</small></div>
        <div><i className={styles.redDot}/><span>Vehicle off road</span><strong>{vor}</strong><small>{vorPct}%</small></div>
        {other > 0 && <div><i className={styles.greyDot}/><span>Other status</span><strong>{other}</strong><small>{percent(other, total)}%</small></div>}
      </div>
    </div>
  </section>;
}

export default function DashboardPanel() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  const [garage, setGarage] = useState(""); const [reason, setReason] = useState(""); const [model, setModel] = useState("");
  const [outliers, setOutliers] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const q = new URLSearchParams();
    if (start) q.set("start", start); if (end) q.set("end", end);
    if (garage) q.set("garage", garage); if (reason) q.set("reason", reason); if (model) q.set("model", model);
    q.set("exclude_outliers", String(outliers)); setBusy(true);
    fetch(`/api/vor/reporting/dashboard?${q}`, { credentials: "same-origin", cache: "no-store" })
      .then(async r => { if (!r.ok) { const e = await r.json().catch(() => ({ detail: `HTTP ${r.status}` })); throw new Error(e.detail || `HTTP ${r.status}`); } return r.json(); })
      .then((d: DashboardData) => { if (!cancelled) { setData(d); setError(""); } })
      .catch(e => { if (!cancelled) setError((e as Error).message); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [start, end, garage, reason, model, outliers]);
  const rows = useMemo(() => data?.cases || [], [data]);
  const download = () => {
    if (!data) return;
    const table: (string | number)[][] = [["Vehicle", "Reason", "Case status", "Opened", "Garage", "Completed case duration (days)"], ...rows.map(c => [c.registration, c.reason, c.status, c.opened_at, c.garage, c.days ?? ""])];
    const csv = table.map(r => r.map(x => `"${String(x).replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = `vor-report-${data.as_of}.csv`; a.click(); URL.revokeObjectURL(url);
  };
  return <main className={styles.page}>
    <header className={styles.heading}><div><h2>Dashboard</h2><p>Live view of fleet performance, VOR trends and operational workload</p></div><button onClick={download} disabled={!data}>↓ Daily VOR report (.csv)</button></header>
    <section className={styles.filters} aria-label="Dashboard filters">
      <label>From<input type="date" value={start} onChange={(e: {target: {value: string}}) => setStart(e.target.value)}/></label><label>To<input type="date" value={end} onChange={(e: {target: {value: string}}) => setEnd(e.target.value)}/></label>
      <label>Workshop<select value={garage} onChange={(e: {target: {value: string}}) => setGarage(e.target.value)}><option value="">All workshops</option>{data?.available_garages.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>VOR reason<select value={reason} onChange={(e: {target: {value: string}}) => setReason(e.target.value)}><option value="">All reasons</option>{data?.available_reasons.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Vehicle model<select value={model} onChange={(e: {target: {value: string}}) => setModel(e.target.value)}><option value="">All models</option>{data?.available_models.map(v => <option key={v}>{v}</option>)}</select></label>
      <label className={styles.toggle}><input type="checkbox" checked={outliers} onChange={(e: {target: {checked: boolean}}) => setOutliers(e.target.checked)}/> Exclude outliers</label>
      <button onClick={() => { setStart(""); setEnd(""); setGarage(""); setReason(""); setModel(""); setOutliers(false); }}>Reset</button>
    </section>
    {busy && <p role="status" className={styles.dataNote}>Refreshing dashboard…</p>}{error && <p role="alert" className={styles.error}>{error}</p>}
    {data && <>
      <section className={styles.metrics} aria-label="Summary KPIs">
        {[
          { n: "Requirement", v: fmt(data.required), sub: "Target vehicles", tone: "neutral", icon: "▤" },
          { n: "Operational today", v: data.operational, sub: "Recorded status", tone: "green", icon: "▣" },
          { n: "VOR today", v: data.vor, sub: "Vehicles", tone: "red", icon: "⚒" },
          { n: "Availability %", v: `${percent(data.operational, data.vehicle_count)}%`, sub: `of ${data.vehicle_count} vehicles`, tone: "green", icon: "◕" },
          { n: "Open issues", v: data.open_cases, sub: "Current issues", tone: "red", icon: "!" },
          { n: "Overdue actions", v: data.overdue, sub: `${data.actions_open} actions open`, tone: "amber", icon: "◷" },
        ].map(x => <article key={x.n} className={`${styles.metric} ${styles[x.tone]}`}><i className={styles.metricIcon} aria-hidden="true">{x.icon}</i><div className={styles.metricText}><small>{x.n}</small><strong>{x.v}</strong><span>{x.sub}</span></div></article>)}
      </section>
      <section className={styles.coverageStrip} aria-label="Required coverage"><span>Operational requirement: <strong>{fmt(data.required)}</strong></span><span>Surplus / shortfall: <strong>{data.deviation == null ? "—" : `${data.deviation > 0 ? "+" : ""}${data.deviation}`}</strong></span>{data.scope_warning && <span>{data.scope_warning}</span>}</section>
      <div className={styles.chartLayout}><TrendChart points={data.trend} description={data.trend_note}/><AvailabilityChart data={data}/></div>
      <div className={styles.secondaryLayout}>
        <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Top VOR reasons · selected period</h3><span className={styles.cardNote}>Selected period</span></div><div className={styles.reasonRows}>{data.counts_by_reason.slice(0,8).map(r => <div key={r.reason} className={styles.reasonRow}><span title={r.reason}>{r.reason}</span><div className={styles.reasonTrack}><i style={{width:`${percent(r.count,Math.max(1,...data.counts_by_reason.map(x=>x.count)))}%`}}/></div><strong>{r.count}</strong></div>)}{!data.counts_by_reason.length && <p>No VOR cases in this period.</p>}</div></section>
        <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Completed case duration</h3><span className={styles.cardNote}>Days · not technician labour time</span></div><div className={styles.durationGrid}>{[{label:"Mean",v:data.case_duration.mean},{label:"Median",v:data.case_duration.median},{label:"P90",v:data.case_duration.p90}].map(x=><div key={x.label}><small>{x.label}</small><strong>{fmt(x.v," d")}</strong></div>)}</div><p className={styles.dataNote}>{data.case_duration_basis} {data.outlier_method} Included: {data.case_duration.retained}; excluded: {data.case_duration.excluded}.</p></section>
        <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Garage workload</h3><span className={styles.cardNote}>Completed cases</span></div><div className={styles.tableScroll}><table><thead><tr><th>Workshop</th><th>Cases</th><th>Median</th></tr></thead><tbody>{data.workshops.slice(0,7).map(w=><tr key={w.garage}><td>{w.garage}</td><td>{w.cases}</td><td>{fmt(w.median," d")}</td></tr>)}</tbody></table></div></section>
      </div>
      <div className={styles.bottomLayout}><section className={styles.chartCard}><div className={styles.cardHeading}><h3>Recent VOR cases</h3><span className={styles.cardNote}>{rows.length} matching cases</span></div><div className={styles.tableScroll}><table><thead><tr><th>Vehicle</th><th>Issue</th><th>Workshop</th><th>Status</th><th>Duration</th></tr></thead><tbody>{rows.slice(0,12).map((c,i)=><tr key={`${c.registration}-${c.opened_at}-${i}`}><td><strong>{c.registration}</strong></td><td>{c.reason}</td><td>{c.garage}</td><td><span className={styles.statusPill}>{c.status}</span></td><td>{fmt(c.days," d")}</td></tr>)}</tbody></table></div></section><section className={styles.chartCard}><h3>Operational priorities</h3><div className={styles.priority}><div><strong>{data.actions_open}</strong><span>Outstanding actions</span></div><div><strong>{data.overdue}</strong><span>Overdue</span></div><div><strong>{data.blockers}</strong><span>Active blockers</span></div><div><strong>{data.open_cases}</strong><span>Open cases</span></div></div><p className={styles.dataNote}>{data.daily_reporting_warning}</p></section></div>
    </>}
  </main>;
}
