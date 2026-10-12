"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Image from "next/image";
import styles from "./vor.module.css";

type Vehicle = {id:number;registration:string;model:string;availability_status:string;severity:string;issue:string;scenario:string;garage:string;vor_days:number;workflow_current_step:number;next_action:string;responsible:string;action_due:string;mot_due:string;inspection_due:string;service_due:string;odometer_miles:number;unread_count:number};
type Ticket = {id:string;vehicle_id:number;kind:string;title:string;status:string;severity:string;scenario:string;key2_reference:string|null;hoth_reference:string|null};
type EventItem = {id:number;vehicle_id:number;ticket_id:string|null;kind:string;author:string;body:string;created_at:string;subject:string|null;recipient_email:string|null;direction:string|null};
type Step = {ticket_id:string;step_index:number;label:string;status:string};
type Contact = {id:number;name:string;email:string;role:"internal"|"external"};
type Subscriber = {vehicle_id:number;contact_id:number};
type Booking = {id:number;vehicle_id:number;kind:string;booked_date:string;garage:string;status:string};
type Daily = {date:string;vor_count:number;fleet_count:number};
type WorkflowTemplate = {code:string;name:string;steps_json:string};
type Data = {workflows:WorkflowTemplate[];vehicles:Vehicle[];tickets:Ticket[];events:EventItem[];steps:Step[];contacts:Contact[];subscriptions:Subscriber[];bookings:Booking[];daily:Daily[];today:string};
type Tab = "vehicles"|"dashboard"|"calendar";
type Filter = "all"|"internal"|"email"|"key2"|"hoth";
const API = "/api/vor";
const FILTERS: Array<{id:Filter;label:string}> = [{id:"all",label:"All activity"},{id:"internal",label:"Internal"},{id:"email",label:"Emails"},{id:"key2",label:"KEY2"},{id:"hoth",label:"HOTH"}];
const TYPES = ["MOT","Inspection","Service"] as const;
const OWNERS = ["Alex Tym","Victoria B.","Jason W.","Janine M.","Gosha T."] as const;
const WORKSHOPS = ["Nursling","Aylesbury","Oxford","Portsmouth","Didcot","Winchester","Reading","Hook","Southampton","Basingstoke"] as const;
const SCENARIO_LABELS: Record<string,string> = {
  engine:"Engine failure",adblue:"AdBlue system",door:"Door mechanism",electrical:"Electrical fault",
  tyre:"Tyre puncture",gearbox:"Gearbox",fuel:"Fuel injection",brakes:"Brakes",
  mot:"MOT",service:"Scheduled service",inspection:"Safety inspection",glass:"Windscreen",
  cooling:"Cooling system"
};
const two = (x:number)=>String(x).padStart(2,"0");
const dgb = (iso:string)=>/^\d{4}-\d\d-\d\d/.test(iso) ? `${iso.slice(8,10)}-${iso.slice(5,7)}-${iso.slice(0,4)}` : iso;
const day = (iso:string)=>new Date(`${iso.slice(0,10)}T12:00:00`);
const plusDays = (iso:string,n:number)=>{const d=day(iso);d.setDate(d.getDate()+n);return `${d.getFullYear()}-${two(d.getMonth()+1)}-${two(d.getDate())}`};
const isoMonth = (y:number,m:number)=>`${y}-${two(m+1)}`;

async function request<T>(path:string,opts?:RequestInit):Promise<T> {
  const result=await fetch(API+path,{credentials:"same-origin",cache:"no-store",...opts,headers:{"Content-Type":"application/json",...opts?.headers}});
  const payload = await result.json().catch(()=>({detail:`HTTP ${result.status}`}));
  if(!result.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `HTTP ${result.status}`);
  return payload as T;
}

function CalendarView({data,book,loading}: {data:Data;book:(v:Vehicle,kind:string)=>void;loading:boolean}) {
 const initial=day(data.today); const [cursor,setCursor]=useState({year:initial.getFullYear(),month:initial.getMonth()});
 const first=new Date(cursor.year,cursor.month,1);const offset=(first.getDay()+6)%7;
 const cells:Array<string|null>=[...Array(offset).fill(null)];
 const days=new Date(cursor.year,cursor.month+1,0).getDate();
 for(let i=1;i<=days;i++) cells.push(`${isoMonth(cursor.year,cursor.month)}-${two(i)}`);
 while(cells.length%7)cells.push(null);
 const visibleBookings = data.bookings.filter(b=>b.booked_date.startsWith(isoMonth(cursor.year,cursor.month)));
 const lookup=(date:string)=>visibleBookings.filter(b=>b.booked_date===date);
 const bound=plusDays(data.today,60);
 const outstanding = data.vehicles.flatMap(v=>TYPES.map(kind=>({v,kind,due:kind==="MOT"?v.mot_due:kind==="Inspection"?v.inspection_due:v.service_due})))
 .filter(x=>x.due<=bound && !data.bookings.some(b=>b.vehicle_id===x.v.id && b.kind===x.kind && b.booked_date>=data.today && b.booked_date<=bound))
 .sort((a,b)=>a.due.localeCompare(b.due));
 const move=(direction:number)=>setCursor(prev=>{const d=new Date(prev.year,prev.month+direction,1);return {year:d.getFullYear(),month:d.getMonth()}});
 return <div className={styles.calendarLayout}>
  <section className={styles.panel}>
   <div className={styles.calendarTop}><div><h2>Maintenance calendar</h2><p>Confirmed bookings · workshop and garage</p></div><a href={`${API}/calendar.ics`} download="fleet-vor-demo.ics" className={styles.exportButton}>↓ Download calendar (.ics)</a><div className={styles.monthControls}><button onClick={()=>move(-1)} aria-label="Previous month">‹</button><strong>{first.toLocaleDateString("en-GB",{month:"long",year:"numeric"})}</strong><button onClick={()=>move(1)} aria-label="Next month">›</button></div></div>
   <div className={styles.calendarGrid}>{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(n=><div className={styles.weekday} key={n}>{n}</div>)}
   {cells.map((c,index)=><div key={`${index}-${c}`} className={`${styles.dayCell} ${c===data.today?styles.isToday:""} ${!c?styles.blankDay:""}`}>
    {c&&<><strong>{Number(c.slice(-2))}</strong>{lookup(c).map(b=>{const v=data.vehicles.find(x=>x.id===b.vehicle_id);return <div className={`${styles.calendarEvent} ${styles[`event${b.kind}` as keyof typeof styles]||""} ${b.booked_date<data.today?styles.overdueEvent:""}`} key={b.id} title={`${b.kind}: ${v?.registration} · ${b.garage}`}><b>{v?.registration}</b><span>{b.kind} · {b.garage}</span></div>})}</>}
   </div>)}</div>
   <p className={styles.calendarFootnote}>Bookings are distinct from due dates. The calendar shows booked MOT, Inspection and Service appointments.</p>
  </section>
  <aside className={`${styles.panel} ${styles.outstandingPanel}`}><div className={styles.panelHeading}><div><h2>Not booked · 60 days</h2><p>Due by {dgb(bound)}, without a confirmed booking</p></div><span className={styles.countBadge}>{outstanding.length}</span></div>
   <div className={styles.outstandingList}>{outstanding.length===0?<p>Everything due within 60 days is booked.</p>:outstanding.map((x,i)=><div className={`${styles.outstandingCard} ${x.due < data.today ? styles.overdueEvent : ""}`} key={`${x.v.id}-${x.kind}-${i}`}><div><strong>{x.v.registration}</strong><span>{x.kind} due {dgb(x.due)}{x.due<data.today?" · OVERDUE":""}</span><small>{x.v.garage}</small></div><button disabled={loading} onClick={()=>book(x.v,x.kind)}>Book</button></div>)}</div>
  </aside>
 </div>;
}

function Dashboard({data}:{data:Data}) {
 const vor=data.vehicles.filter(v=>v.availability_status==="VOR");const available=data.vehicles.length-vor.length;
 const avg=vor.length?(vor.reduce((n,v)=>n+v.vor_days,0)/vor.length).toFixed(1):"0";
 const due=data.vehicles.filter(v=>v.action_due <= data.today && v.availability_status==="VOR").length;
 const counts=Object.entries(vor.reduce<Record<string,number>>((a,v)=>(a[v.scenario]=(a[v.scenario]||0)+1,a),{})).sort((a,b)=>b[1]-a[1]);
 const w=640,h=175,pad=20;const points=data.daily.map((d,i)=>`${pad+(i/Math.max(1,data.daily.length-1))*(w-2*pad)},${h-pad-(d.vor_count/Math.max(1,...data.daily.map(x=>x.vor_count)))*(h-2*pad)}`).join(" ");
 return <div className={styles.dashboardView}>
  <div className={styles.metrics}>{[{n:"Fleet size",v:data.vehicles.length,sub:"Synthetic vehicles"},{n:"Vehicles off road",v:vor.length,sub:`${Math.round(vor.length/data.vehicles.length*100)}% of fleet`},{n:"Average VOR duration",v:`${avg} d`,sub:"Current VOR cases"},{n:"Actions due / overdue",v:due,sub:"VOR follow-ups"}].map(k=><div className={styles.metric} key={k.n}><small>{k.n}</small><b>{k.v}</b><span>{k.sub}</span></div>)}</div>
  <div className={styles.chartGrid}><section className={styles.panel}><h2>VOR trend · last 30 days</h2><p>Historical synthetic figures</p><div className={styles.lineChart}><svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="VOR trend" preserveAspectRatio="none"><line x1={pad} y1={h-pad} x2={w-pad} y2={h-pad} stroke="#d8ddcd" strokeWidth="2"/><polyline fill="none" stroke="#596246" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" points={points}/></svg></div><div className={styles.chartDates}><span>{dgb(data.daily[0]?.date||data.today)}</span><span>{dgb(data.today)}</span></div></section>
   <section className={styles.panel}><h2>Fleet availability</h2><p>Operational / Vehicle off road</p><div className={styles.donutRow}><div className={styles.donut} style={{background:`conic-gradient(#596246 0 ${available/data.vehicles.length*100}%, #B96063 ${available/data.vehicles.length*100}% 100%)`}}><span>{Math.round(available/data.vehicles.length*100)}%</span></div><div className={styles.legend}><span><i style={{background:"#596246"}}/>Operational <b>{available}</b></span><span><i style={{background:"#B96063"}}/>VOR <b>{vor.length}</b></span></div></div></section>
   <section className={styles.panel}><h2>Active VOR by fault type</h2><p>Grouped by repair workflow</p><div className={styles.bars}>{counts.map(([kind,n])=><div key={kind} className={styles.barRow}><span>{kind.replaceAll("_"," ")}</span><div><i style={{width:`${n/vor.length*100}%`}}/></div><strong>{n}</strong></div>)}</div></section>
   <section className={styles.panel}><h2>Operational priorities</h2><p>Longest-running current cases</p><div className={styles.priorityList}>{[...vor].sort((a,b)=>b.vor_days-a.vor_days).slice(0,5).map(v=><div key={v.id}><strong>{v.registration}</strong><span>{v.issue}</span><b>{v.vor_days}d</b></div>)}</div></section>
  </div>
 </div>;
}

export default function VorHub() {
 const [session,setSession]=useState<{enabled:boolean;authenticated:boolean;liveEmail:boolean}|null>(null);
 const [password,setPassword]=useState("");const [loginError,setLoginError]=useState("");
 const [data,setData]=useState<Data|null>(null);const [view,setView]=useState<Tab>("vehicles");
 const [reg,setReg]=useState<string>("GX24 KLM");const [search,setSearch]=useState("");
 const [filter,setFilter]=useState<Filter>("all");const [ticketFilter,setTicketFilter]=useState<string>("all");
 const [composeKind,setComposeKind]=useState<"internal"|"email">("internal");const [message,setMessage]=useState("");
 const [subject,setSubject]=useState("");
 const [busy,setBusy]=useState(false);const [notice,setNotice]=useState("");const [showPeople,setShowPeople]=useState(false);
 
 const [bookingForm,setBookingForm]=useState<{vehicle:Vehicle;kind:string}|null>(null);
 const [bookingDate,setBookingDate]=useState("");const [bookingGarage,setBookingGarage]=useState("");
 const [clock,setClock]=useState(0);
 const [contactName,setContactName]=useState("");
 const [contactEmail,setContactEmail]=useState("");
 const [contactRole,setContactRole]=useState<"internal"|"external">("internal");
 const [editContactId,setEditContactId]=useState<number|null>(null);
 const [workflowExpanded,setWorkflowExpanded]=useState(false);
 const load = useCallback(async ()=>{const payload=await request<Data>("/bootstrap");setData(payload);setClock(c=>c+1)},[]);
 useEffect(()=>{request<{enabled:boolean;authenticated:boolean;liveEmail:boolean}>("/session").then(s=>{setSession(s);if(s.authenticated) load().catch(e=>setNotice(e.message))}).catch(e=>setLoginError(e.message))},[load]);
 const login=async(e:FormEvent)=>{e.preventDefault();setLoginError("");setBusy(true);try{await request("/login",{method:"POST",body:JSON.stringify({password})});setSession(x=>({...x!,authenticated:true}));setPassword("");await load()}catch(err){setLoginError((err as Error).message)}finally{setBusy(false)}};
 const mutate=async(path:string,body:object,after?:()=>void)=>{setBusy(true);setNotice("");try{await request(path,{method:"POST",body:JSON.stringify(body)});await load();after?.()}catch(err){setNotice((err as Error).message)}finally{setBusy(false)}};
 const selected=data?.vehicles.find(v=>v.registration===reg)||data?.vehicles[0];
 const tickets=(data?.tickets||[]).filter(t=>t.vehicle_id===selected?.id);
 const primary=tickets.find(t=>t.id===ticketFilter&&t.status==="open")||tickets.find(t=>t.status==="open")||tickets[0];
 const currentSteps=(data?.steps||[]).filter(s=>s.ticket_id===primary?.id).sort((a,b)=>a.step_index-b.step_index);
 const doneStages=currentSteps.filter(s=>s.status==="done").length;
 const currentStage=currentSteps.find(s=>s.status==="current");
 const events=(data?.events||[]).filter(e=>e.vehicle_id===selected?.id && (filter==="all"||filter===e.kind) && (ticketFilter==="all"||(ticketFilter==="vehicle-only"?!e.ticket_id:e.ticket_id===ticketFilter))).sort((a,b)=>a.created_at.localeCompare(b.created_at)).slice(-80);
 const selectedContacts=(data?.subscriptions||[]).filter(s=>s.vehicle_id===selected?.id).map(s=>data?.contacts.find(c=>c.id===s.contact_id)).filter((c):c is Contact=>Boolean(c));
 const shown=(data?.vehicles||[]).filter(v=>`${v.registration} ${v.model} ${v.issue} ${v.garage}`.toLowerCase().includes(search.toLowerCase()));
 const post=()=>{if(!selected||!message.trim())return;
   if(composeKind==="email"&&selectedContacts.length===0){setNotice("Add subscribers to the vehicle first");return;}
   mutate("/messages",{vehicle_id:selected.id,ticket_id:ticketFilter==="vehicle-only"?null:(ticketFilter==="all"?primary?.id:ticketFilter)||null,kind:composeKind,text:message.trim(),subject:composeKind==="email"?subject:null},()=>{setMessage("");setSubject("");setNotice(composeKind==="email"?(session?.liveEmail?"Notification sent to vehicle subscribers":"Notification simulated for all subscribers and saved in Chatter"):"Internal note saved")})
 };
 const clearContactForm=()=>{setEditContactId(null);setContactName("");setContactEmail("");setContactRole("internal")};
 const selectContactForEdit=(c:Contact)=>{setEditContactId(c.id);setContactName(c.name);setContactEmail(c.email);setContactRole(c.role)};
 const saveContact=async(e:FormEvent<HTMLFormElement>)=>{
   e.preventDefault();if(!selected||!contactName.trim()||!contactEmail.trim())return;
   setBusy(true);setNotice("");
   try {
     const body={name:contactName.trim(),email:contactEmail.trim().toLowerCase(),role:contactRole};
     if(editContactId!==null) {
       await request(`/contacts/${editContactId}/update`,{method:"POST",body:JSON.stringify(body)});
     } else {
       const created=await request<{id:number}>("/contacts",{method:"POST",body:JSON.stringify(body)});
       await request("/subscribers",{method:"POST",body:JSON.stringify({vehicle_id:selected.id,contact_id:created.id,subscribed:true})});
     }
     await load();clearContactForm();setNotice("Contact saved and subscriber list updated");
   } catch(err) {setNotice((err as Error).message)} finally {setBusy(false)}
 };
 const openBook=(v:Vehicle,kind:string)=>{setBookingForm({vehicle:v,kind});setBookingDate(kind==="MOT"?v.mot_due:kind==="Inspection"?v.inspection_due:v.service_due);setBookingGarage(v.garage)};
 if(!session)return <div className={styles.root}><div className={styles.loginCard}>Connecting to Fleet VOR Hub… {loginError}</div></div>;
 if(!session.enabled)return <div className={styles.root}><div className={styles.loginCard}><h2>Fleet VOR Hub disabled</h2><p>Set VOR_DEMO_ENABLED=true in backend environment.</p></div></div>;
 if(!session.authenticated)return <div className={styles.root}><form onSubmit={login} className={styles.loginCard}><div className={styles.logo}>SCAS <small>FLEET · DEMO</small></div><h1>Fleet VOR Hub</h1><p>Private demonstration · enter the access password</p><input autoFocus type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Demo password" aria-label="Demo password" required/><button disabled={busy} type="submit">{busy?"Checking…":"Enter Fleet Hub"}</button>{loginError&&<p className={styles.error}>{loginError}</p>}</form></div>;
 if(!data)return <div className={styles.root}><div className={styles.loginCard}>Loading demo records… {notice}</div></div>;
 return <div className={styles.root}>
  <header className={styles.header}><div className={styles.brand}><div className={styles.logo}>SCAS <small>FLEET</small></div><div><strong>Fleet VOR Hub</strong><small>Vehicle-centred issues and communications workspace</small></div></div><nav className={styles.nav} aria-label="Fleet Hub pages"><button className={view==="vehicles"?styles.navActive:""} onClick={()=>setView("vehicles")}>Vehicles</button><button className={view==="dashboard"?styles.navActive:""} onClick={()=>setView("dashboard")}>Dashboard</button><button className={view==="calendar"?styles.navActive:""} onClick={()=>setView("calendar")}>Calendar</button></nav><div className={styles.headerRight}><a className={styles.exportButton} href={`${API}/export.xlsx`} download="fleet-vor-demo.xlsx" title="Download Excel workbook">↓ Excel</a><span className={styles.demoBadge}>Demo v1</span><span className={styles.profile}><Image src="/images/profile/alex.webp" alt="Alex Tymoshenko" width={28} height={28} className={styles.avatar} />Alex Tymoshenko</span><button className={styles.logout} onClick={()=>request("/logout",{method:"POST",body:"{}"}).finally(()=>{setSession(s=>({...s!,authenticated:false}));setData(null)})}>Log out</button></div></header>
  {notice&&<div role="status" className={styles.toast} onClick={()=>setNotice("")}>{notice} ×</div>}
  {view==="dashboard"?<Dashboard data={data}/>:view==="calendar"?<CalendarView data={data} book={openBook} loading={busy}/>:<main className={styles.workspace}>
    <aside className={`${styles.panel} ${styles.vehiclePane}`}><div className={styles.sideHeader}><div className={styles.panelHeading}><div><h2>Vehicles</h2><p>{shown.length} vehicles shown</p></div><span className={styles.critical}>{data.vehicles.filter(x=>x.severity==="Critical"&&x.availability_status==="VOR").length} critical</span></div><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="⌕  Reg, model, issue, garage…" aria-label="Search vehicles"/></div><div className={styles.vehicleScroll}>{shown.map(v=><button key={v.id} onClick={()=>{setReg(v.registration);setTicketFilter("all");setFilter("all")}} className={`${styles.vehicleCard} ${v.registration===selected?.registration?styles.vehicleSelected:""}`} data-severity={v.severity.toLowerCase()}><div className={styles.vehicleTitle}><b>{v.registration}</b>{v.unread_count>0&&<span className={styles.unread}>{v.unread_count}</span>}</div><small>{v.model}</small><div className={styles.cardStatus}><span className={v.availability_status==="VOR"?styles.statusVor:styles.statusOperational}>{v.availability_status}</span><span>{v.vor_days?v.vor_days+" days":"Available"}</span></div><p>{v.issue}</p><div className={styles.vehicleWorkshop}><span>Workshop</span><strong>{v.garage}</strong></div></button>)}</div></aside>
      <div className={`${styles.panel} ${styles.details}`}>
       <div className={styles.detailsHead}><div><div className={styles.pills}><span className={selected?.availability_status==="VOR"?styles.statusVor:styles.statusOperational}>{selected?.availability_status}</span><span className={styles.severity}>{selected?.severity}</span></div><h1>{selected?.registration}</h1><p>{selected?.model}</p><div className={styles.ticketRowHead}><small>LINKED TICKETS</small><div>{tickets.map(t=><button title={`${t.title} · ${t.status}`} key={t.id} onClick={()=>setTicketFilter(t.id)} className={`${styles.ticketChip} ${ticketFilter===t.id?styles.ticketChosen:""}`}>{t.id}</button>)}</div></div></div><span className={styles.miniMeta}>Odometer <strong>{selected?.odometer_miles.toLocaleString("en-GB")} mi</strong></span></div>
       <div className={styles.detailsBody}>
        <div className={styles.problemLabel}>CURRENT PROBLEM</div><div className={styles.issueBox}>{selected?.issue}</div>
        <div className={styles.infoPair}><div><label htmlFor="vor-workshop">WORKSHOP</label><select id="vor-workshop" className={styles.responsibleSelect} value={selected?.garage||""} disabled={busy} onChange={e=>selected&&mutate("/workshop",{vehicle_id:selected.id,garage:e.target.value})}>{Array.from(new Set([...(data?.vehicles||[]).map(v=>v.garage), ...WORKSHOPS])).sort().map(g=><option key={g} value={g}>{g}</option>)}</select></div><div><label htmlFor="vor-responsible">RESPONSIBLE</label><select id="vor-responsible" className={styles.responsibleSelect} value={selected?.responsible||""} disabled={busy} onChange={e=>selected&&mutate("/responsible",{vehicle_id:selected.id,name:e.target.value})}>{OWNERS.map(n=><option key={n} value={n}>{n}</option>)}</select></div></div>
        <div className={styles.maintenanceInside}><div className={styles.maintenanceTitle}>MAINTENANCE &amp; COMPLIANCE</div><div className={styles.maintenanceGrid}>{([{key:"MOT",d:selected?.mot_due},{key:"Inspection",d:selected?.inspection_due},{key:"Service",d:selected?.service_due}] as const).map(x=><div key={x.key} className={x.d&&x.d<data.today?styles.overdueEvent:""}><small>{x.key}{x.d&&x.d<data.today?" · OVERDUE":""}</small><strong>{dgb(x.d||"")}</strong><button onClick={()=>selected&&openBook(selected,x.key)}>Book / view</button></div>)}</div></div>
       </div>
      </div>
    <section className={styles.middlePane}>
      <div className={styles.workflow}>
       <div className={styles.workflowTopRow}><div className={styles.panelHeading}><h2>Breakdown / service workflow</h2><span>{doneStages}/{currentSteps.length} stages</span></div><div className={styles.workflowHeaderActions}><button className={styles.workflowCompleteBtn} disabled={busy||!currentStage||!primary||primary.status!=="open"} onClick={()=>selected&&primary&&mutate("/advance",{vehicle_id:selected.id,ticket_id:primary.id})}>Complete stage</button><button type="button" className={styles.workflowToggle} aria-expanded={workflowExpanded} onClick={()=>setWorkflowExpanded(v=>!v)}>{workflowExpanded?"▾":"▸"}</button></div></div>
       {workflowExpanded&&<div className={styles.scenarioRow}><label htmlFor="vor-scenario">Repair / service scenario</label><select id="vor-scenario" value={primary?.scenario||""} disabled={busy||!primary||primary.status!=="open"} onChange={e=>{if(!selected||!primary)return;const code=e.target.value;if(code===primary.scenario)return;if(!window.confirm(`Change workflow to ${SCENARIO_LABELS[code]||code}? Current stage progress for ${primary.id} will restart.`))return;mutate("/scenario",{vehicle_id:selected.id,ticket_id:primary.id,scenario:code})}}>{data.workflows.map(w=><option key={w.code} value={w.code}>{SCENARIO_LABELS[w.code]||w.name}</option>)}</select><small>{primary?.id}</small></div>}
       <ol className={styles.workflowStages}>{currentSteps.map(s=><li key={`${primary?.id}-${s.step_index}`} className={s.status==="done"?styles.stageDone:s.status==="current"?styles.stageCurrent:styles.stagePending}><span className={styles.stageMarker}>{s.status==="done"?"✓":s.step_index+1}</span><span className={styles.stageLabel}>{s.label}</span>{s.status==="current"&&<b>NOW</b>}</li>)}</ol>
       {currentSteps.length===0&&<p className={styles.workflowEmpty}>No stages assigned to this ticket.</p>}
      </div>
    </section>
    <section className={`${styles.panel} ${styles.chatterPane}`}><div className={styles.chatterTop}><div className={styles.panelHeading}><div><h2>Communication history · All sources</h2></div><span className={styles.linkedCount}>{tickets.length} linked tickets</span></div><div className={styles.subscribers}><div className={styles.subscriberTop}><strong>SUBSCRIBERS</strong><button onClick={()=>setShowPeople(v=>!v)}>{showPeople?"Close":"Manage"}</button></div><div className={styles.subscriberGroups}><div><small>INTERNAL</small><div>{selectedContacts.filter(c=>c.role==="internal").map(c=><span title={c.email} key={c.id} className={styles.personChip}>{c.name}</span>)}</div></div><div><small>EXTERNAL</small><div>{selectedContacts.filter(c=>c.role==="external").map(c=><span title={c.email} key={c.id} className={styles.externalChip}>{c.name}</span>)}</div></div></div></div>
    {showPeople&&<div className={styles.manageContacts}>
      <div className={styles.manageIntro}>Manage contacts and emails for this vehicle. Only checked subscribers receive updates.</div>
      <div className={styles.contactList}>{data.contacts.map(c=><div key={c.id} className={styles.contactDirectoryRow}><label><input type="checkbox" disabled={busy} checked={selectedContacts.some(x=>x.id===c.id)} onChange={e=>selected&&mutate("/subscribers",{vehicle_id:selected.id,contact_id:c.id,subscribed:e.target.checked})}/><span><strong>{c.name}</strong><small>{c.email}</small></span></label><button type="button" disabled={busy} onClick={()=>selectContactForEdit(c)}>Edit</button></div>)}</div>
      <form className={styles.contactForm} onSubmit={saveContact}>
        <strong>{editContactId===null?"Add email contact":"Edit email contact"}</strong>
        <input aria-label="Contact name" required maxLength={80} placeholder="Name" value={contactName} onChange={e=>setContactName(e.target.value)}/>
        <input type="email" aria-label="Contact email" required maxLength={254} placeholder="Email address" value={contactEmail} onChange={e=>setContactEmail(e.target.value)}/>
        <select aria-label="Contact type" value={contactRole} onChange={e=>setContactRole(e.target.value as "internal"|"external")}><option value="internal">Internal</option><option value="external">External</option></select>
        <button type="submit" disabled={busy||!contactName.trim()||!contactEmail.trim()}>{editContactId===null?"Add & subscribe":"Save contact"}</button>
        {editContactId!==null&&<button type="button" onClick={clearContactForm}>Cancel edit</button>}
      </form>
    </div>}
    <div className={styles.filterBar}>{FILTERS.map(f=><button key={f.id} onClick={()=>setFilter(f.id)} className={filter===f.id?styles.filterActive:""}>{f.label}</button>)}</div><div className={styles.ticketFilter}>Ticket: <select value={ticketFilter} onChange={e=>setTicketFilter(e.target.value)}><option value="all">All vehicle activity</option><option value="vehicle-only">Vehicle only (no ticket)</option>{tickets.map(t=><option key={t.id} value={t.id}>{t.id}</option>)}</select></div></div>
     <div className={styles.timeline} key={`${selected?.id}-${filter}-${ticketFilter}-${clock}`}>{events.map(e=><div key={e.id} className={`${styles.event} ${e.author==="Alex"?styles.eventMine:""}`}><div className={styles.eventMeta}><b>{e.author}</b><span>{e.kind.toUpperCase()}</span>{e.ticket_id&&<em>{e.ticket_id}</em>}</div>{e.subject&&<strong className={styles.eventSubject}>{e.subject}</strong>}<p>{e.body}</p>{e.recipient_email&&<small>Recipients: {e.recipient_email} · {e.direction==="simulated_outgoing"?"Simulated":"Email"}</small>}<time>{e.created_at.replace("T"," ").slice(0,16)}</time></div>)}{events.length===0&&<div className={styles.emptyActivity}>No activity with these filters</div>}</div>
     <div className={styles.compose}><div className={styles.composeTabs}><button onClick={()=>setComposeKind("internal")} className={composeKind==="internal"?styles.composeActive:""}>Internal note</button><button onClick={()=>setComposeKind("email")} className={composeKind==="email"?styles.composeActive:""}>All subscribers</button><span>{session.liveEmail?"Live email enabled":"Email simulation"}</span></div>
      {composeKind==="email"&&<div className={styles.emailFields}><div className={styles.recipientSummary}><strong>To all vehicle subscribers ({selectedContacts.length})</strong><small>{selectedContacts.map(c=>c.email).join(", ") || "No subscribers — manage subscribers first"}</small></div><input aria-label="Email subject" placeholder="Subject" value={subject} onChange={e=>setSubject(e.target.value)} /></div>}
      <div className={styles.composeBottom}><textarea value={message} onChange={e=>setMessage(e.target.value)} placeholder={composeKind==="email"?"Write an email…":"Write an internal update…"}/><button aria-label="Save message" disabled={busy||!message.trim()||(composeKind==="email"&&selectedContacts.length===0)} onClick={post}>{busy?"…":"➤"}</button></div>
     </div>
    </section>
  </main>}
  {bookingForm&&<div className={styles.modalBackdrop} role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setBookingForm(null)}}><form className={styles.bookModal} onSubmit={e=>{e.preventDefault();mutate("/bookings",{vehicle_id:bookingForm.vehicle.id,kind:bookingForm.kind,booked_date:bookingDate,garage:bookingGarage},()=>setBookingForm(null))}}><h2>Book {bookingForm.kind}</h2><p>{bookingForm.vehicle.registration} · {bookingForm.vehicle.model}</p><label>Date<input type="date" min={data.today} value={bookingDate} onChange={e=>setBookingDate(e.target.value)} required/></label><label>Garage<input value={bookingGarage} onChange={e=>setBookingGarage(e.target.value)} required/></label><div><button type="button" onClick={()=>setBookingForm(null)}>Cancel</button><button disabled={busy} type="submit">Save booking</button></div></form></div>}
 </div>;
}
