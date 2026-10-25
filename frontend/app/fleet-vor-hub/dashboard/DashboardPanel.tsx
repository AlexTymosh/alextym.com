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
type FleetSnapshot = {
  vehicles: {id:number;registration:string;garage:string;mot_due:string;inspection_due:string;service_due:string;availability_status?:string;issue?:string}[];
  tickets: {id:string;status:string;vehicle_id:number}[];
  steps: {ticket_id:string;label:string;status:string}[];
  bookings: {vehicle_id:number;kind:string;booked_date:string}[];
};
const fmt = (value: number | null, suffix = "") => value == null ? "—" : `${value}${suffix}`;
const percent = (a: number, b: number) => b > 0 ? Math.round(a / b * 1000) / 10 : 0;

function TrendChart({points}: {points:TrendPoint[]}) {
  const [range,setRange] = useState("30");
  const rows=points.slice(-Number(range));
  const max=Math.max(5,...rows.map(p=>Math.max(p.vor,p.non_vor_proxy)));
  const w=900,h=255,x0=42,x1=w-15,y0=15,y1=h-34;
  const y=(n:number)=>y1-(n/max)*(y1-y0);
  const x=(i:number)=>x0+i/Math.max(1,rows.length-1)*(x1-x0);
  const line=(key:"vor"|"non_vor_proxy")=>rows.map((p,i)=>`${i?"L":"M"}${x(i).toFixed(2)},${y(p[key]).toFixed(2)}`).join(" ");
  const dateLabel=(v:string)=>new Date(`${v.slice(0,10)}T12:00:00`).toLocaleDateString("en-GB",{day:"2-digit",month:"short"});
  const xTicks=rows.map((_,i)=>i).filter((i)=>i===0||i===rows.length-1||i%Math.max(1,Math.ceil(rows.length/9))===0);
  const yTicks=Array.from({length:6},(_,i)=>Math.round(i*max/5));
  return <section className={styles.chartCard} aria-label="VOR trend chart">
    <div className={styles.cardHeading}><h3>VOR trend · last {range} days <span title="Green is a calculated non-VOR count, not confirmed daily deployment." aria-label="Historic trend method" className={styles.chartInfo}>ⓘ</span></h3>
      <div className={styles.chartLegend}><span><i className={styles.legendRed}/> VOR vehicles</span><span><i className={styles.legendGreen}/> Non-VOR vehicles</span>
      <select aria-label="Trend period" value={range} onChange={(e:{target:{value:string}})=>setRange(e.target.value)}><option value="7">7 days</option><option value="14">14 days</option><option value="30">30 days</option></select></div>
    </div>
    {rows.length?<svg viewBox={`0 0 ${w} ${h}`} className={styles.lineGraph} role="img" aria-label="Daily VOR count and calculated non-VOR count">
      <defs><linearGradient id="vor-trend-red" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#fa737b" stopOpacity=".25"/><stop offset="100%" stopColor="#fa737b" stopOpacity=".015"/></linearGradient>
      <linearGradient id="vor-trend-green" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#50ae7c" stopOpacity=".22"/><stop offset="100%" stopColor="#50ae7c" stopOpacity=".015"/></linearGradient></defs>
      {yTicks.map((n,i)=><g key={i}><line x1={x0} x2={x1} y1={y(n)} y2={y(n)} stroke="#e4ebf1" strokeWidth="1"/><text x={x0-9} y={y(n)+4} textAnchor="end" fontSize="11" fill="#718698">{n}</text></g>)}
      {xTicks.map(i=><g key={i}><line x1={x(i)} x2={x(i)} y1={y0} y2={y1} stroke="#edf1f5"/><text x={x(i)} y={h-9} textAnchor={i===0?"start":i===rows.length-1?"end":"middle"} fontSize="11" fill="#718698">{dateLabel(rows[i].date)}</text></g>)}
      <path d={`${line("non_vor_proxy")} L${x(rows.length-1)},${y1} L${x0},${y1} Z`} fill="url(#vor-trend-green)"/>
      <path d={`${line("vor")} L${x(rows.length-1)},${y1} L${x0},${y1} Z`} fill="url(#vor-trend-red)"/>
      <path d={line("non_vor_proxy")} stroke="#41a673" strokeWidth="2.7" fill="none" strokeLinejoin="round"/>
      <path d={line("vor")} stroke="#f26470" strokeWidth="2.7" fill="none" strokeLinejoin="round"/>
      {rows.map((p,i)=><g key={p.date}><circle cx={x(i)} cy={y(p.vor)} r="2.9" fill="#f26470"><title>{dateLabel(p.date)}: {p.vor} VOR</title></circle><circle cx={x(i)} cy={y(p.non_vor_proxy)} r="2.9" fill="#41a673"><title>{dateLabel(p.date)}: {p.non_vor_proxy} non-VOR</title></circle></g>)}
    </svg>:<p className={styles.emptyChart}>No recorded historical trend for this period.</p>}
  </section>;
}

function AvailabilityChart({data,snapshot}: {data:DashboardData;snapshot:FleetSnapshot|null}) {
  const total=data.vehicle_count;
  const assigned=new Map<string,string>();
  if(snapshot)for(const ticket of snapshot.tickets.filter(t=>t.status==="open")) {
    const step=snapshot.steps.find(x=>x.ticket_id===ticket.id&&x.status==="current");
    const label=(step?.label||"").toLowerCase();
    const kind=/part|quot|approv|authoris|estimate|waiting|supplier/.test(label)?"Awaiting parts / quote":/workshop|repair|diagnos|service|inspection|road test/.test(label)?"In workshop":"Off road (other)";
    const previous=assigned.get(String(ticket.vehicle_id));
    if(!previous || previous==="Off road (other)") assigned.set(String(ticket.vehicle_id),kind);
  }
  let inWorkshop=0,waiting=0;
  if(snapshot)for(const v of snapshot.vehicles.filter(v=>v.availability_status==="VOR")) {
    const kind=assigned.get(String(v.id)); if(kind==="In workshop")inWorkshop++;else if(kind==="Awaiting parts / quote")waiting++;
  }
  inWorkshop=Math.min(inWorkshop,data.vor);
  waiting=Math.min(waiting,Math.max(0,data.vor-inWorkshop));
  const segments=[
    {name:"Operational",count:Math.max(0,data.operational),color:"#42a979"},
    {name:"In workshop",count:inWorkshop,color:"#65aafa"},
    {name:"Awaiting parts / quote",count:waiting,color:"#f5b951"},
    {name:"Off road (other)",count:Math.max(0,data.vor-inWorkshop-waiting),color:"#f46972"},
    {name:"Other recorded status",count:Math.max(0,total-data.operational-data.vor),color:"#a9b6bf"}
  ];
  let angle=0;
  const stops=segments.map(s=>{const from=angle;angle+=percent(s.count,total);return `${s.color} ${from}% ${angle}%`;}).join(", ");
  const opPct=Math.round(percent(data.operational,total));
  return <section className={styles.chartCard} aria-label="Fleet availability chart">
    <div className={styles.cardHeading}><h3>Fleet availability</h3><span className={styles.cardNote} title="Workshop and parts categories are inferred from active workflow labels; the official vehicle status remains unchanged.">Current fleet · ⓘ</span></div>
    <div className={styles.donutLayout}><div className={styles.donut} style={{background:total?`conic-gradient(${stops})`:"#e8edf1"}} role="img" aria-label={segments.map(s=>`${s.name}: ${s.count}`).join(", ")}><div className={styles.donutHole}><strong>{opPct}%</strong><span>Operational</span><small>{data.operational} of {total}</small></div></div>
    <div className={styles.donutLegend}>{segments.filter(s=>s.count>0).map(s=><div key={s.name}><i style={{background:s.color}}/><span>{s.name}</span><strong>{s.count}</strong><small>{Math.round(percent(s.count,total))}%</small></div>)}</div></div>
  </section>;
}

const classifyIssue=(issue:string):string=>{
  if(/gearbox|transmission|clutch|shifting|slipping/i.test(issue))return "Gearbox / transmission";
  if(/adblue|emission|exhaust|dpf/i.test(issue))return "Emissions / AdBlue";
  if(/inject|engine|start|misfire|oil|fuel|coolant/i.test(issue))return "Engine / fuel system";
  if(/brake|abs|pressure/i.test(issue))return "Braking system";
  if(/battery|alternator|electric|wiring|power/i.test(issue))return "Electrical fault";
  if(/tyre|puncture|wheel/i.test(issue))return "Tyre damage";
  if(/door|window|windscreen|glass|lock/i.test(issue))return "Body / glazing";
  if(/inspection|mot|service/i.test(issue))return "Scheduled maintenance";
  return "Unclassified";
};
const STAGE_GROUPS:[RegExp,string][]=[
  [/part|supplier|quote|quotat|estimate/i,"Awaiting parts / quotation"],
  [/diagnos|fault|inspect/i,"Diagnosis"],
  [/approv|authoris/i,"Approval"],
  [/workshop|book|recovery|recover/i,"Workshop / recovery"],
  [/repair|replace|work|service perform/i,"Repair in progress"],
  [/test|check|quality|safety/i,"Testing / safety checks"],
  [/document|record|hoth|clos|notification/i,"Documentation / closure"],
  [/requested|registered|report/i,"Defect registered"],
];

export default function DashboardPanel() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [snapshot, setSnapshot] = useState<FleetSnapshot | null>(null);
  useEffect(() => {
    let cancelled=false;
    fetch("/api/vor/bootstrap",{credentials:"same-origin",cache:"no-store"})
      .then(async r=>r.ok?await r.json() as FleetSnapshot:null)
      .then(value=>{if(!cancelled&&value&&Array.isArray(value.vehicles))setSnapshot(value)})
      .catch(()=>{});
    return ()=>{cancelled=true};
  },[]);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [start, setStart] = useState(() => { const d=new Date(); d.setDate(d.getDate()-29); return d.toISOString().slice(0,10); }); const [end, setEnd] = useState("");
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
  const stageDistribution = useMemo(() => {
    if (!snapshot) return [] as {label:string;count:number}[];
    const counts = new Map<string,number>();
    for (const ticket of snapshot.tickets.filter(t=>t.status==="open")) {
      const stage=snapshot.steps.find(step=>step.ticket_id===ticket.id && step.status==="current");
      const key=stage?.label || "Unassigned";
      counts.set(key,(counts.get(key)||0)+1);
    }
    const grouped=new Map<string,number>();
    for(const [label,count] of Array.from(counts)){const category=STAGE_GROUPS.find(([re])=>re.test(label))?.[1]||"Other";grouped.set(category,(grouped.get(category)||0)+count);}
    return Array.from(grouped,([label,count])=>({label,count})).sort((a,b)=>b.count-a.count);
  },[snapshot]);
  const reasonRows=useMemo(()=>{
    if(!data)return [] as {reason:string;count:number}[];
    const issueByRegistration=new Map(snapshot?.vehicles.map(v=>[v.registration.toUpperCase(),v.issue||""])||[]);
    const grouped=new Map<string,number>();
    // Preserve stored reasons. Categorise Unknown using defect descriptions solely for this chart.
    for(const c of data.cases){
      let category=c.reason||"Unclassified";
      if(/unknown|under investigation|unclassified/i.test(category))category=classifyIssue(issueByRegistration.get(c.registration.toUpperCase())||"");
      grouped.set(category,(grouped.get(category)||0)+1);
    }
    return Array.from(grouped,([reason,count])=>({reason,count})).sort((a,b)=>b.count-a.count);
  },[data,snapshot]);
  const garageLoad=useMemo(()=>{
    if(!snapshot)return [] as {garage:string;count:number}[];
    const garages=new Map(snapshot.vehicles.map(v=>[v.id,v.garage]));
    const counts=new Map<string,number>();
    for(const ticket of snapshot.tickets.filter(t=>t.status==="open")){const g=garages.get(ticket.vehicle_id)||"Unassigned";counts.set(g,(counts.get(g)||0)+1);}
    return Array.from(counts,([garage,count])=>({garage,count})).sort((a,b)=>b.count-a.count).slice(0,6);
  },[snapshot]);
  const bookingRisk = useMemo(() => {
    if (!snapshot||!data) return [] as {registration:string;kind:string;date:string;garage:string}[];
    const end=new Date(`${data.as_of.slice(0,10)}T12:00:00`);end.setDate(end.getDate()+14);
    const until=`${end.getFullYear()}-${String(end.getMonth()+1).padStart(2,"0")}-${String(end.getDate()).padStart(2,"0")}`;
    return snapshot.vehicles.flatMap(v=>[{kind:"MOT",date:v.mot_due},{kind:"Inspection",date:v.inspection_due},{kind:"Service",date:v.service_due}]
      .filter(x=>x.date&&x.date<=until && !snapshot.bookings.some(b=>b.vehicle_id===v.id&&b.kind===x.kind&&b.booked_date>=data.as_of.slice(0,10)&&b.booked_date<=until))
      .map(x=>({...x,registration:v.registration,garage:v.garage}))).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,6);
  },[snapshot,data]);
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
      <button onClick={() => { setStart((()=>{const d=new Date();d.setDate(d.getDate()-29);return d.toISOString().slice(0,10);})()); setEnd(""); setGarage(""); setReason(""); setModel(""); setOutliers(false); }}>Reset</button>
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
      <div className={styles.chartLayout}><TrendChart points={data.trend}/><AvailabilityChart data={data} snapshot={snapshot}/></div>
      <div className={styles.secondaryLayout}>
        <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Top VOR reasons · last 30 days</h3><span className={styles.cardNote} title="Unknown reasons are grouped from vehicle defect descriptions when available.">Cases in selected filters · ⓘ</span></div><div className={styles.reasonRows}>{reasonRows.slice(0,8).map((r,i)=><div key={r.reason} className={styles.reasonRow}><span title={r.reason}>{r.reason}</span><div className={styles.reasonTrack}><i style={{width:`${percent(r.count,Math.max(1,...reasonRows.map(x=>x.count)))}%`,background:["#f36c73","#f7aa64","#70a9f3","#a995ee","#59b59b","#54c5c9","#abb7c0"][i%7]}}/></div><strong>{r.count}</strong><small>{Math.round(percent(r.count,reasonRows.reduce((a,b)=>a+b.count,0)))}%</small></div>)}{!reasonRows.length&&<p>No VOR cases in this period.</p>}</div></section>
        <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Repair stage distribution</h3><span className={styles.cardNote}>Open tickets · current stage</span></div>{snapshot?<div className={styles.stageSummary}>{stageDistribution.slice(0,8).map((item,index)=><div key={item.label} className={styles.stageRow}><span title={item.label}>{item.label}</span><div className={styles.stageTrack}><i style={{width:`${percent(item.count,Math.max(1,...stageDistribution.map(x=>x.count)))}%`,background:["#72abeb","#61bd96","#f5b857","#f08883","#a89bf4","#64bccb","#a3b5bf"][index%7]}}/></div><strong>{item.count}</strong><small>{Math.round(percent(item.count,stageDistribution.reduce((a,b)=>a+b.count,0)))}%</small></div>)}{!stageDistribution.length&&<p className={styles.dataNote}>No open tickets with recorded stages.</p>}</div>:<p className={styles.dataNote}>Stage detail unavailable.</p>}</section>
        <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Garage workload</h3><span className={styles.cardNote}>Open repair cases</span></div>{garageLoad.length?<div className={styles.garageBars}>{garageLoad.map((g,i)=><div className={styles.garageColumn} key={g.garage}><div className={styles.garageValue}>{g.count}</div><div className={styles.garageBar} style={{height:`${Math.max(7,percent(g.count,Math.max(1,...garageLoad.map(x=>x.count))))}%`,background:["#50b588","#62a5f7","#ffc15e","#f47a7f","#b69aef","#70bccb"][i]}}/><span title={g.garage}>{g.garage}</span></div>)}</div>:<p className={styles.dataNote}>No active workshop assignments.</p>}</section>
        {data.case_duration.retained > 0 && <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Completed case duration</h3><span className={styles.cardNote}>Days · not technician labour time</span></div><div className={styles.durationGrid}>{[{label:"Mean",v:data.case_duration.mean},{label:"Median",v:data.case_duration.median},{label:"P90",v:data.case_duration.p90}].map(x=><div key={x.label}><small>{x.label}</small><strong>{fmt(x.v," d")}</strong></div>)}</div><p className={styles.dataNote}>{data.case_duration_basis} {data.outlier_method} Included: {data.case_duration.retained}; excluded: {data.case_duration.excluded}.</p></section>}
        {data.workshops.length > 0 && <section className={styles.chartCard}><div className={styles.cardHeading}><h3>Garage duration comparison</h3><span className={styles.cardNote}>Completed cases</span></div><div className={styles.tableScroll}><table><thead><tr><th>Workshop</th><th>Cases</th><th>Median</th></tr></thead><tbody>{data.workshops.slice(0,7).map(w=><tr key={w.garage}><td>{w.garage}</td><td>{w.cases}</td><td>{fmt(w.median," d")}</td></tr>)}</tbody></table></div></section>}
      </div>
      <div className={styles.bottomLayout}><section className={styles.chartCard}><div className={styles.cardHeading}><h3>Recent VOR cases</h3><span className={styles.cardNote}>{rows.length} matching cases</span></div><div className={styles.tableScroll}><table><thead><tr><th>Vehicle</th><th>Issue</th><th>Workshop</th><th>Status</th><th>Duration</th></tr></thead><tbody>{rows.slice(0,12).map((c,i)=><tr key={`${c.registration}-${c.opened_at}-${i}`}><td><strong>{c.registration}</strong></td><td>{c.reason}</td><td>{c.garage}</td><td><span className={styles.statusPill}>{c.status}</span></td><td>{fmt(c.days," d")}</td></tr>)}</tbody></table></div></section><section className={styles.chartCard}><div className={styles.cardHeading}><h3>Upcoming bookings at risk</h3><span className={styles.cardNote}>Fleet-wide · next 14 days</span></div>{snapshot?<div className={styles.tableScroll}><table><thead><tr><th>Due</th><th>Vehicle</th><th>Type</th><th>Base</th><th>Status</th></tr></thead><tbody>{bookingRisk.map((x,i)=><tr key={`${x.registration}-${x.kind}-${i}`}><td>{x.date}</td><td><strong>{x.registration}</strong></td><td>{x.kind}</td><td>{x.garage}</td><td><span className={styles.riskPill}>{x.date < data.as_of.slice(0,10)?"Overdue":"Unbooked"}</span></td></tr>)}</tbody></table>{!bookingRisk.length&&<p className={styles.dataNote}>No unbooked maintenance due in this period.</p>}</div>:<p className={styles.dataNote}>Booking snapshot unavailable.</p>}</section>
      <section className={styles.chartCard}><h3>Operational priorities</h3><div className={styles.priority}><div><strong>{data.actions_open}</strong><span>Outstanding actions</span></div><div><strong>{data.overdue}</strong><span>Overdue</span></div><div><strong>{data.blockers}</strong><span>Active blockers</span></div><div><strong>{data.open_cases}</strong><span>Open cases</span></div></div><p className={styles.dataNote}>{data.daily_reporting_warning}</p></section></div>
    </>}
  </main>;
}
