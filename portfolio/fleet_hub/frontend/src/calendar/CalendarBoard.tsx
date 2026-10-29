"use client";

import { useMemo, useState } from "react";
import styles from "./calendar-board.module.css";

type Vehicle = { id: number; registration: string; model: string; garage: string; mot_due: string; inspection_due: string; service_due: string };
type Booking = { id: number; vehicle_id: number; kind: string; booked_date: string; garage: string; status: string };
type Props = { data: { vehicles: Vehicle[]; bookings: Booking[]; today: string }; loading: boolean; bookVehicle: (vehicleId: number, kind: string) => void };
type Due = { vehicle: Vehicle; kind: string; date: string };
const TYPES = ["MOT", "Inspection", "Service"] as const;
const pad = (value: number) => String(value).padStart(2,"0");
const iso = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}`;
const parse = (value: string) => new Date(`${value.slice(0,10)}T12:00:00`);
const nice = (value: string) => /^\d{4}-\d\d-\d\d/.test(value) ? parse(value).toLocaleDateString("en-GB",{day:"numeric",month:"short"}) : "—";
const dueValue = (v: Vehicle, kind: string) => kind==="MOT" ? v.mot_due : kind==="Inspection" ? v.inspection_due : v.service_due;
const getMonday = (date: Date) => { const d=new Date(date); d.setDate(d.getDate()-((d.getDay()+6)%7)); return d; };

export default function CalendarBoard({data,loading,bookVehicle}:Props) {
  const [date,setDate]=useState(()=>parse(data.today));
  const [mode,setMode]=useState<"month"|"week"|"list">("month");
  const [leftMode,setLeftMode]=useState<"due"|"all">("due");
  const [search,setSearch]=useState("");
  const [base,setBase]=useState("");
  const [partner,setPartner]=useState("");
  const [type,setType]=useState("");
  const [selected,setSelected]=useState<number|null>(null);
  const first=new Date(date.getFullYear(),date.getMonth(),1);
  const monthTitle=date.toLocaleDateString("en-GB",{month:"long",year:"numeric"});
  const bases=Array.from(new Set(data.vehicles.map(v=>v.garage))).sort();
  const partners=Array.from(new Set(data.bookings.map(b=>b.garage))).sort();
  const byId=new Map(data.vehicles.map(v=>[v.id,v]));
  const matches=(v:Vehicle)=> (!base||v.garage===base) && `${v.registration} ${v.model} ${v.garage}`.toLowerCase().includes(search.toLowerCase());
  const bookings=data.bookings.filter(b=> (!partner||b.garage===partner)&&(!type||b.kind===type) && (byId.get(b.vehicle_id)?matches(byId.get(b.vehicle_id)!):false));
  const boundary=new Date(parse(data.today));boundary.setDate(boundary.getDate()+60);
  const pending=useMemo(()=>data.vehicles.flatMap(v=>TYPES.map(kind=>({vehicle:v,kind,date:dueValue(v,kind)})))
    .filter(x=>x.date && x.date<=iso(boundary) && matches(x.vehicle) && (!type||x.kind===type) && !data.bookings.some(b=>b.vehicle_id===x.vehicle.id&&b.kind===x.kind&&b.booked_date>=data.today&&b.booked_date<=iso(boundary)))
    .sort((a,b)=>a.date.localeCompare(b.date)),[data,search,base,type]);
  const allVehicles=data.vehicles.filter(matches).sort((a,b)=>a.registration.localeCompare(b.registration));
  const weeks=()=>{const start=getMonday(first);const finish=new Date(date.getFullYear(),date.getMonth()+1,0);const result:string[]=[];for(let d=start;d<=finish || result.length%7!==0;d=new Date(d.getFullYear(),d.getMonth(),d.getDate()+1)){ result.push(iso(d)); }return result;};
  const weekStart=getMonday(date);const days=mode==="week"?Array.from({length:7},(_,i)=>iso(new Date(weekStart.getFullYear(),weekStart.getMonth(),weekStart.getDate()+i))):weeks();
  const listed=bookings.filter(b=>mode==="week"?days.includes(b.booked_date):b.booked_date.slice(0,7)===iso(first).slice(0,7)).sort((a,b)=>a.booked_date.localeCompare(b.booked_date));
  const move=(count:number)=>setDate(old=>mode==="week"?new Date(old.getFullYear(),old.getMonth(),old.getDate()+7*count):new Date(old.getFullYear(),old.getMonth()+count,1));
  const bookingCard=(b:Booking)=>{const v=byId.get(b.vehicle_id);return <button type="button" key={b.id} className={`${styles.appointment} ${styles[b.kind.toLowerCase() as "mot"|"inspection"|"service"]||""}`} title={`${v?.registration||"Vehicle"} · ${b.kind} · ${b.garage}`} onClick={()=>setSelected(b.vehicle_id)}><strong>{v?.registration||"Unknown"}</strong><span>{b.kind}</span><small>{b.garage}</small></button>;};
  const startBooking=(vehicleId:number,kind:string)=>{setSelected(vehicleId);bookVehicle(vehicleId,kind);};
  return <main className={styles.root}>
    <aside className={styles.rail} aria-label="Vehicle booking queue">
      <h2>Vehicles</h2>
      <div className={styles.search}><input aria-label="Search calendar vehicles" placeholder="Search vehicles…" value={search} onChange={(e: {target:{value:string}})=>setSearch(e.target.value)}/><span aria-hidden="true">⌕</span></div>
      <div className={styles.railTabs}><button type="button" className={leftMode==="due"?styles.active:""} onClick={()=>setLeftMode("due")}>Due / Unbooked <b>{pending.length}</b></button><button type="button" className={leftMode==="all"?styles.active:""} onClick={()=>setLeftMode("all")}>All Vehicles</button></div>
      <div className={styles.railList}>{leftMode==="due" ? pending.map((x,i)=><article key={`${x.vehicle.id}-${x.kind}-${i}`} className={x.vehicle.id===selected?styles.chosen:""}><div className={styles.railCardTop}><strong>{x.vehicle.registration}</strong><span className={`${styles.typePill} ${styles[x.kind.toLowerCase() as "mot"|"inspection"|"service"]||""}`}>{x.kind}</span></div><small>{x.vehicle.model}</small><p className={x.date < data.today?styles.danger:""}>{x.date<data.today?"Overdue": "Due"} · {nice(x.date)}</p><footer><span>⌖ {x.vehicle.garage}</span><button type="button" disabled={loading} onClick={()=>startBooking(x.vehicle.id,x.kind)}>+ Book {x.kind}</button></footer></article>) : allVehicles.map(v=><article className={v.id===selected?styles.chosen:""} key={v.id}><div className={styles.railCardTop}><strong>{v.registration}</strong></div><small>{v.model}</small><p>⌖ {v.garage}</p><footer><span>Next: {nice([v.mot_due,v.inspection_due,v.service_due].filter(Boolean).sort()[0]||"")}</span><button type="button" disabled={loading} onClick={()=>startBooking(v.id,"MOT")}>+ Book</button></footer></article>)}{(leftMode==="due"?pending.length:allVehicles.length)===0&&<p className={styles.empty}>No vehicles match these filters.</p>}</div>
    </aside>
    <section className={styles.board}>
      <header className={styles.heading}><div><h2>Calendar</h2><p>Manage workshop bookings, inspections, MOTs and servicing across the fleet.</p></div><a href="/api/vor/calendar.ics" download="fleet-vor-demo.ics">↓ Export calendar</a></header>
      <div className={styles.filters}><label>Vehicle base<select value={base} onChange={(e: {target:{value:string}})=>setBase(e.target.value)}><option value="">All bases</option>{bases.map(x=><option key={x} value={x}>{x}</option>)}</select></label><label>Partner / booked garage<select value={partner} onChange={(e: {target:{value:string}})=>setPartner(e.target.value)}><option value="">All partners</option>{partners.map(x=><option key={x} value={x}>{x}</option>)}</select></label><label>Booking type<select value={type} onChange={(e: {target:{value:string}})=>setType(e.target.value)}><option value="">All types</option>{TYPES.map(x=><option key={x} value={x}>{x}</option>)}</select></label><button type="button" onClick={()=>{setBase("");setPartner("");setType("");setSearch("");}}>Clear filters</button><button type="button" className={styles.newBooking} disabled={loading||data.vehicles.length===0} onClick={()=>startBooking(selected??data.vehicles[0].id,"MOT")}>+ New booking</button></div>
      <section className={styles.calendar}><div className={styles.monthHeader}><div className={styles.navigation}><button aria-label="Previous period" onClick={()=>move(-1)}>‹</button><button onClick={()=>setDate(parse(data.today))}>Today</button><button aria-label="Next period" onClick={()=>move(1)}>›</button><h3>{mode==="week"?`${nice(days[0])} – ${nice(days[6])}`:monthTitle}</h3></div><div className={styles.modes}>{(["month","week","list"] as const).map(m=><button key={m} onClick={()=>setMode(m)} className={mode===m?styles.modeActive:""} aria-pressed={mode===m}>{m[0].toUpperCase()+m.slice(1)}</button>)}</div></div>
      {mode!=="list"?<div className={`${styles.grid} ${mode==="week"?styles.oneWeek:""}`} style={{gridTemplateRows:`32px repeat(${days.length/7}, minmax(${mode==="week"?"400px":"96px"}, 1fr))`}}>{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(x=><span className={styles.weekDay} key={x}>{x}</span>)}{days.map(d=><div key={d} className={`${styles.cell} ${d===data.today?styles.today:""} ${d.slice(0,7)!==iso(first).slice(0,7) && mode==="month"?styles.adjacent:""}`}><button type="button" aria-label={`Select ${d}`} className={styles.dayNum} onClick={()=>setDate(parse(d))}>{Number(d.slice(-2))}</button>{bookings.filter(b=>b.booked_date===d).map(bookingCard)}</div>)}</div>:<div className={styles.listView}>{listed.length?listed.map(b=><div key={b.id} className={styles.listEntry}><strong>{nice(b.booked_date)}</strong>{bookingCard(b)}</div>):<p className={styles.empty}>No bookings in this period.</p>}</div>}
      </section><p className={styles.note}>Recorded booking dates only; time slots are not available in this demonstration. Due dates and confirmed bookings are separate.</p>
    </section>
  </main>;
}
