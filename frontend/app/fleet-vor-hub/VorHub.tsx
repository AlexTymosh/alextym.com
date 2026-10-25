/* PR12 MESSAGE CARD HOOK */
// PR09 APPROVED MOCKUP REDESIGN
"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Image from "next/image";
import styles from "./vor.module.css";
import MessageCard from "./message-card/MessageCard";
import VehiclePhoto from "./vehicle-photo/VehiclePhoto";
import CalendarBoard from "./calendar/CalendarBoard";
import ManagementDashboard from "./dashboard/DashboardPanel";
import OperationsPanel from "./operations/OperationsPanel";
import AssetSignals,{type OpsIndicator} from "./operations/AssetSignals";

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
const FILTERS: Array<{id:Filter;label:string}> = [{id:"all",label:"All activity"},{id:"internal",label:"Internal"},{id:"email",label:"Emails"},{id:"key2",label:"Status log"},{id:"hoth",label:"HOTH"}];
const TYPES = ["MOT","Inspection","Service"] as const;
const OWNERS = ["Alex Tym","Victoria B.","Jason W.","Janine M.","Gosha T."] as const;
const WORKSHOPS = ["Nursling","Aylesbury","Oxford","Portsmouth","Didcot","Winchester","Reading","Hook","Southampton","Basingstoke"] as const;
const SCENARIO_LABELS: Record<string,string> = {
  engine:"Engine failure",adblue:"AdBlue system",door:"Door mechanism",electrical:"Electrical fault",
  tyre:"Tyre puncture",gearbox:"Gearbox",fuel:"Fuel injection",brakes:"Brakes",
  mot:"MOT",service:"Scheduled service",inspection:"Safety inspection",glass:"Windscreen",
  cooling:"Cooling system"
};

// The checklist is stored in v2 SQLite; its keys are validated by the backend.
const WORKFLOW_ITEMS: Record<number,{key:string;label:string;type?:"date"}[]> = {
  0:[{key:"notification_sent",label:"Details sent to service company"},{key:"response_received",label:"Acknowledgement received"}],
  1:[{key:"information_forwarded",label:"Defect information passed on"},{key:"visit_date_agreed",label:"Inspection date agreed"},{key:"diagnosis_date",label:"Agreed date",type:"date"},{key:"maintenance_combination_reviewed",label:"Combining with MOT / inspection / service checked"}],
  2:[{key:"inspected",label:"Specialist inspection completed"},{key:"initial_quote_received",label:"Initial quotation received"},{key:"preliminary_estimate_confirmed",label:"Preliminary estimate confirmed"}],
  3:[{key:"approval_recorded",label:"Repair authorised"}],
  4:[{key:"work_started",label:"Work started"},{key:"repair_finished",label:"Work completed"}],
  5:[{key:"repair_verified",label:"Repair completion confirmed"},{key:"release_checked",label:"Release and safety checks completed"}],
  6:[{key:"hoth_informed",label:"Operations desk notified"},{key:"hoth_closed_confirmed",label:"Ticket closure confirmed"}],
  7:[{key:"documents_received",label:"Post-repair documents received"},{key:"documents_checked",label:"Documents reviewed"}],
};
type ChecklistItem = {step_index:number;key:string;checked:boolean;value:string|null};

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

 const [cityFilter,setCityFilter]=useState("all");
 const [partnerFilter,setPartnerFilter]=useState("all");
 const [typeFilter,setTypeFilter]=useState("all");
 const vehicleBase=(id:number)=>data.vehicles.find(v=>v.id===id)?.garage||"Unassigned";
 const cities=Array.from(new Set(data.bookings.map(b=>vehicleBase(b.vehicle_id)))).sort();
 const partners=Array.from(new Set(data.bookings.map(b=>b.garage))).sort();
 const first=new Date(cursor.year,cursor.month,1);const offset=(first.getDay()+6)%7;
 const cells:Array<string|null>=[...Array(offset).fill(null)];
 const days=new Date(cursor.year,cursor.month+1,0).getDate();
 for(let i=1;i<=days;i++) cells.push(`${isoMonth(cursor.year,cursor.month)}-${two(i)}`);
 while(cells.length%7)cells.push(null);
 const visibleBookings = data.bookings.filter(b=>b.booked_date.startsWith(isoMonth(cursor.year,cursor.month)) && (cityFilter==="all"||vehicleBase(b.vehicle_id)===cityFilter) && (partnerFilter==="all"||b.garage===partnerFilter) && (typeFilter==="all"||b.kind===typeFilter));
 const lookup=(date:string)=>visibleBookings.filter(b=>b.booked_date===date);
 const bound=plusDays(data.today,60);
 const outstanding = data.vehicles.flatMap(v=>TYPES.map(kind=>({v,kind,due:kind==="MOT"?v.mot_due:kind==="Inspection"?v.inspection_due:v.service_due})))
 .filter(x=>x.due<=bound && !data.bookings.some(b=>b.vehicle_id===x.v.id && b.kind===x.kind && b.booked_date>=data.today && b.booked_date<=bound))
 .sort((a,b)=>a.due.localeCompare(b.due));
 const move=(direction:number)=>setCursor(prev=>{const d=new Date(prev.year,prev.month+direction,1);return {year:d.getFullYear(),month:d.getMonth()}});
 return <div className={styles.calendarLayout}>
  <section className={styles.panel}>
   <div className={styles.calendarTop}><div><h2>Maintenance calendar</h2><p>Confirmed bookings · workshop and garage</p></div><a href={`${API}/calendar.ics`} download="fleet-vor-demo.ics" className={styles.exportButton}>↓ Download calendar (.ics)</a><div className={styles.monthControls}><button onClick={()=>move(-1)} aria-label="Previous month">‹</button><strong>{first.toLocaleDateString("en-GB",{month:"long",year:"numeric"})}</strong><button onClick={()=>move(1)} aria-label="Next month">›</button></div></div>

   <div className={styles.calendarFilters} aria-label="Calendar booking filters">
    <label>City / vehicle base<select value={cityFilter} onChange={e=>setCityFilter(e.target.value)}><option value="all">All bases</option>{cities.map(c=><option key={c} value={c}>{c}</option>)}</select></label>
    <label>Partner / booked garage<select value={partnerFilter} onChange={e=>setPartnerFilter(e.target.value)}><option value="all">All partners</option>{partners.map(g=><option key={g} value={g}>{g}</option>)}</select></label>
    <label>Booking type<select value={typeFilter} onChange={e=>setTypeFilter(e.target.value)}><option value="all">All types</option>{TYPES.map(t=><option key={t} value={t}>{t}</option>)}</select></label>
    <button type="button" onClick={()=>{setCityFilter("all");setPartnerFilter("all");setTypeFilter("all")}}>Clear filters</button>
   </div>
   <div className={styles.calendarGrid} style={{gridTemplateRows:`32px repeat(${Math.ceil(cells.length/7)}, minmax(110px, 1fr))`}}>{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(n=><div className={styles.weekday} key={n}>{n}</div>)}
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
   <section className={styles.panel}><h2>Fleet availability</h2><p>Operational / Vehicle off road</p><div className={styles.donutRow}><div className={styles.donut} style={{background:`conic-gradient(#596246 0 ${available/data.vehicles.length*100}%, #b18b53 ${available/data.vehicles.length*100}% 100%)`}}><span>{Math.round(available/data.vehicles.length*100)}%</span></div><div className={styles.legend}><span><i style={{background:"#596246"}}/>Operational <b>{available}</b></span><span><i style={{background:"#b18b53"}}/>VOR <b>{vor.length}</b></span></div></div></section>
   <section className={styles.panel}><h2>Active VOR by fault type</h2><p>Grouped by repair workflow</p><div className={styles.bars}>{counts.map(([kind,n])=><div key={kind} className={styles.barRow}><span>{kind.replaceAll("_"," ")}</span><div><i style={{width:`${n/vor.length*100}%`}}/></div><strong>{n}</strong></div>)}</div></section>
   <section className={styles.panel}><h2>Operational priorities</h2><p>Longest-running current cases</p><div className={styles.priorityList}>{[...vor].sort((a,b)=>b.vor_days-a.vor_days).slice(0,5).map(v=><div key={v.id}><strong>{v.registration}</strong><span>{v.issue}</span><b>{v.vor_days}d</b></div>)}</div></section>
  </div>
 </div>;
}

export default function VorHub({embedded=false,externalView,initialVehicle,onAuthChange}:{embedded?:boolean;externalView?:Tab;initialVehicle?:string|null;onAuthChange?:(authenticated:boolean)=>void}={}) {
 // PR0405: case-based operational control and asset signals
 const [opsOverview,setOpsOverview]=useState<Record<string,OpsIndicator>>({});
 const [session,setSession]=useState<{enabled:boolean;authenticated:boolean;liveEmail:boolean}|null>(null);
 const [password,setPassword]=useState("");const [loginError,setLoginError]=useState("");
 const [data,setData]=useState<Data|null>(null);const [view,setView]=useState<Tab>("vehicles");
 const [reg,setReg]=useState<string>("GX24 KLM");const [search,setSearch]=useState("");
 useEffect(()=>{if(externalView)setView(externalView)},[externalView]);
 useEffect(()=>{if(initialVehicle)setReg(initialVehicle)},[initialVehicle]);
 const [railMode,setRailMode]=useState<"vehicles"|"tickets">("vehicles");
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
 const [workflowExpanded,setWorkflowExpanded]=useState(true);
 const [expandedStage,setExpandedStage]=useState<number|null>(null);
 const [showSubscribers,setShowSubscribers]=useState(false);
 const timelineRef = useRef<HTMLDivElement>(null);
 const load = useCallback(async ()=>{const payload=await request<Data>("/bootstrap");setData(payload);request<{vehicles:Record<string,OpsIndicator>}>("/ops/overview").then(r=>setOpsOverview(r.vehicles)).catch(()=>setOpsOverview({}));setClock(c=>c+1)},[]);
 useEffect(()=>{request<{enabled:boolean;authenticated:boolean;liveEmail:boolean}>("/session").then(s=>{setSession(s);onAuthChange?.(s.authenticated);if(s.authenticated) load().catch(e=>setNotice(e.message))}).catch(e=>setLoginError(e.message))},[load]);
 const login=async(e:FormEvent)=>{e.preventDefault();setLoginError("");setBusy(true);try{await request("/login",{method:"POST",body:JSON.stringify({password})});setSession(x=>({...x!,authenticated:true}));onAuthChange?.(true);setPassword("");await load()}catch(err){setLoginError((err as Error).message)}finally{setBusy(false)}};
 const mutate=async(path:string,body:object,after?:()=>void)=>{setBusy(true);setNotice("");try{await request(path,{method:"POST",body:JSON.stringify(body)});await load();after?.()}catch(err){setNotice((err as Error).message)}finally{setBusy(false)}};
 useEffect(()=>{const requested=new URLSearchParams(window.location.search).get("vehicle");if(requested)setReg(requested);},[]);
 const selected=data?.vehicles.find(v=>v.registration===reg)||data?.vehicles[0];
 const tickets=(data?.tickets||[]).filter(t=>t.vehicle_id===selected?.id);
 const primary=tickets.find(t=>t.id===ticketFilter)||tickets.find(t=>t.status==="open")||tickets[0];
 const ticketIndex=tickets.findIndex(t=>t.id===primary?.id);
 const currentSteps=(data?.steps||[]).filter(s=>s.ticket_id===primary?.id).sort((a,b)=>a.step_index-b.step_index);

 const [checklist,setChecklist]=useState<Record<string,{checked:boolean;value:string|null}>>({});
 const [savingChecklist,setSavingChecklist]=useState(false);
 const [configuredStages,setConfiguredStages]=useState<Record<number,{key:string;label:string;required?:boolean;type?:"date"}[]>>({});
 useEffect(()=>{if(!session?.authenticated)return;
   request<{items:{stage_index:number;item_key:string;label:string;required:boolean}[]}>('/ops/templates')
      .then(r=>{const byStage:Record<number,{key:string;label:string;required?:boolean;type?:"date"}[]>={};
        for(const item of r.items){(byStage[item.stage_index]??=[]).push({key:item.item_key,label:item.label,required:item.required,type:item.item_key==="diagnosis_date"?"date":undefined});}
        setConfiguredStages(byStage);}).catch(()=>{});
 },[session?.authenticated]);
 const stageList=(i:number):{key:string;label:string;required?:boolean;type?:"date"}[]=>configuredStages[i]||WORKFLOW_ITEMS[i]||[];

 useEffect(()=>{let active=true;
   if(!primary?.id){setChecklist({});return;}
   request<{items:ChecklistItem[]}>(`/checklists/${encodeURIComponent(primary.id)}`)
     .then(r=>{if(active)setChecklist(Object.fromEntries(r.items.map(x=>[`${x.step_index}:${x.key}`,{checked:x.checked,value:x.value}])));})
     .catch(e=>{if(active)setNotice((e as Error).message)});
   return()=>{active=false};
 },[primary?.id,clock]);
 const checklistReady=(index:number)=>stageList(index).filter(item=>item.required!==false).every(item=>checklist[`${index}:${item.key}`]?.checked);
 const saveChecklist=async(index:number,key:string,checked:boolean,value:string|null=null)=>{
   if(!selected||!primary)return;
   setSavingChecklist(true);
   try{await request('/checklists',{method:'POST',body:JSON.stringify({vehicle_id:selected.id,ticket_id:primary.id,step_index:index,key,checked,value})});
     setChecklist(prev=>({...prev,[`${index}:${key}`]:{checked,value}}));
   }catch(e){setNotice((e as Error).message)}finally{setSavingChecklist(false)}
 };
 const doneStages=currentSteps.filter(s=>s.status==="done"||s.status==="skipped").length;
 const currentStage=currentSteps.find(s=>s.status==="current");
 const canAdvanceStage=Boolean(selected&&primary?.status==="open"&&currentStage&&!busy&&!savingChecklist&&checklistReady(currentStage.step_index));
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
 useEffect(()=>{if(timelineRef.current)timelineRef.current.scrollTop=timelineRef.current.scrollHeight;},[selected?.id,filter,ticketFilter,clock]);
 const openBook=(v:Vehicle,kind:string)=>{setBookingForm({vehicle:v,kind});setBookingDate(kind==="MOT"?v.mot_due:kind==="Inspection"?v.inspection_due:v.service_due);setBookingGarage(v.garage)};
 if(!session)return <div className={styles.root}><div className={styles.loginCard}>Connecting to Fleet VOR Hub… {loginError}</div></div>;
 if(!session.enabled)return <div className={styles.root}><div className={styles.loginCard}><h2>Fleet VOR Hub disabled</h2><p>Set VOR_DEMO_ENABLED=true in backend environment.</p></div></div>;
 if(!session.authenticated)return <div className={styles.root}><form onSubmit={login} className={styles.loginCard}><div className={styles.logo}>SCAS <small>FLEET · DEMO</small></div><h1>Fleet VOR Hub</h1><p>Private demonstration · enter the access password</p><input autoFocus type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Demo password" aria-label="Demo password" required/><button disabled={busy} type="submit">{busy?"Checking…":"Enter Fleet Hub"}</button>{loginError&&<p className={styles.error}>{loginError}</p>}</form></div>;
 if(!data)return <div className={styles.root}><div className={styles.loginCard}>Loading demo records… {notice}</div></div>;
 return <div className={`${styles.root} ${embedded?styles.embeddedRoot:""}`}>
  {!embedded&&<header className={styles.header}><div className={styles.brand}><div className={styles.logo}>SCAS <small>FLEET</small></div><div><strong>Fleet VOR Hub</strong><small>Vehicle-centred issues and communications workspace</small></div></div><nav className={styles.nav} aria-label="Fleet Hub pages"><button className={view==="vehicles"?styles.navActive:""} onClick={()=>setView("vehicles")}>Vehicles</button><button className={view==="dashboard"?styles.navActive:""} onClick={()=>setView("dashboard")}>Dashboard</button><button className={view==="calendar"?styles.navActive:""} onClick={()=>setView("calendar")}>Calendar</button></nav><div className={styles.headerRight}><a className={styles.exportButton} href={`${API}/export.xlsx`} download="fleet-vor-demo.xlsx" title="Download Excel workbook">↓ Excel</a><a className={styles.exportButton} href="/fleet-vor-hub/register" title="Vehicle register and imports">Vehicle Register</a><a className={styles.exportButton} href="/fleet-vor-hub/new-defect" title="Register OSD / HOTH notification">+ New Defect</a><a className={styles.exportButton} href="/fleet-vor-hub/process" title="AS-IS and TO-BE process mapping">Process Design</a><span className={styles.demoBadge}>Demo v2</span><span className={styles.profile}><Image src="/images/profile/alex.webp" alt="Alex Tymoshenko" width={28} height={28} className={styles.avatar} />Alex Tymoshenko</span><button className={styles.logout} onClick={()=>request("/logout",{method:"POST",body:"{}"}).finally(()=>{setSession(s=>({...s!,authenticated:false}));setData(null)})}>Log out</button></div></header>}
  {notice&&<div role="status" className={styles.toast} onClick={()=>setNotice("")}>{notice} ×</div>}
  {view==="dashboard"?<ManagementDashboard/>:view==="calendar"?<CalendarBoard data={data} loading={busy} bookVehicle={(id,kind)=>{const vehicle=data.vehicles.find(x=>x.id===id);if(vehicle)openBook(vehicle,kind);}}/>:<main className={styles.workspace}>
    <aside className={`${styles.panel} ${styles.vehiclePane}`}><div className={styles.sideHeader}><div className={styles.railTabs} role="tablist" aria-label="Issue list view"><button type="button" role="tab" aria-selected={railMode==="vehicles"} className={railMode==="vehicles"?styles.railSelected:""} onClick={()=>setRailMode("vehicles")}>Vehicles</button><button type="button" role="tab" aria-selected={railMode==="tickets"} className={railMode==="tickets"?styles.railSelected:""} onClick={()=>setRailMode("tickets")}>Tickets</button></div><div className={styles.panelHeading}><div><h2>{railMode==="vehicles"?"Vehicles":"Tickets"}</h2><p>{railMode==="vehicles"?shown.length:(data?.tickets||[]).length} {railMode==="vehicles"?"vehicles":"tickets"} shown</p></div></div><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="⌕  Reg, model, issue, garage…" aria-label="Search vehicles"/></div><div className={styles.vehicleScroll}>{railMode==="vehicles"?shown.map(v=><button key={v.id} onClick={()=>{setReg(v.registration);setTicketFilter("all");setFilter("all")}} className={`${styles.vehicleCard} ${v.registration===selected?.registration?styles.vehicleSelected:""}`} data-severity={v.severity.toLowerCase()}><div className={styles.vehicleTitle}><b>{v.registration}</b>{v.unread_count>0&&<span className={styles.unread}>{v.unread_count}</span>}</div><small>{v.model}</small><div className={styles.cardStatus}><span className={v.availability_status==="VOR"?styles.statusVor:styles.statusOperational}>{v.availability_status}</span><span>{v.vor_days?v.vor_days+" days":"Available"}</span></div><p>{v.issue}</p><div className={styles.vehicleWorkshop}><span>Workshop</span><strong>{v.garage}</strong></div><AssetSignals value={opsOverview[String(v.id)]}/></button>) : (data?.tickets||[]).filter(t=>{
      const v=data?.vehicles.find(x=>x.id===t.vehicle_id);
      return `${t.id} ${t.title} ${v?.registration||""}`.toLowerCase().includes(search.toLowerCase());
    }).map(t=>{
      const v=data?.vehicles.find(x=>x.id===t.vehicle_id);
      return <button key={t.id} type="button" className={`${styles.ticketRailCard} ${primary?.id===t.id?styles.ticketRailSelected:""}`}
        onClick={()=>{if(v)setReg(v.registration);setTicketFilter(t.id);setFilter("all")}}>
        <strong>{t.id}</strong><small>{v?.registration||"Unknown vehicle"} · {t.kind}</small>
        <span title={t.title}>{t.title}</span><em>{t.status}</em>
      </button>;
    })}</div></aside>
      <div className={styles.contentPane}>
      <div className={styles.caseColumn}>
      <div className={`${styles.panel} ${styles.details}`}>
       <div className={styles.detailsHead}><VehiclePhoto model={selected?.model||""} registration={selected?.registration||""}/><div><div className={styles.pills}><span className={selected?.availability_status==="VOR"?styles.statusVor:styles.statusOperational}>{selected?.availability_status}</span><span className={styles.severity}>{selected?.severity}</span></div><h1>{selected?.registration}</h1><p>{selected?.model}</p></div><span className={styles.miniMeta}>Odometer <strong>{selected?.odometer_miles.toLocaleString("en-GB")} mi</strong></span></div>
       <div className={styles.detailsBody}>
        <div className={styles.problemGroup}><div className={styles.problemLabel}>CURRENT PROBLEM</div><div className={styles.issueBox}>{selected?.issue}</div><div className={styles.ticketRowHead}><small>LINKED TICKETS</small><div>{tickets.map(t=><button title={`${t.title} · ${t.status}`} key={t.id} onClick={()=>setTicketFilter(t.id)} className={`${styles.ticketChip} ${ticketFilter===t.id?styles.ticketChosen:""}`}>{t.id}</button>)}</div></div></div>
        <div className={styles.infoPair}><div><label htmlFor="vor-workshop">WORKSHOP</label><select id="vor-workshop" className={styles.responsibleSelect} value={selected?.garage||""} disabled={busy} onChange={e=>selected&&mutate("/workshop",{vehicle_id:selected.id,garage:e.target.value})}>{Array.from(new Set([...(data?.vehicles||[]).map(v=>v.garage), ...WORKSHOPS])).sort().map(g=><option key={g} value={g}>{g}</option>)}</select></div><div><label htmlFor="vor-responsible">RESPONSIBLE</label><select id="vor-responsible" className={styles.responsibleSelect} value={selected?.responsible||""} disabled={busy} onChange={e=>selected&&mutate("/responsible",{vehicle_id:selected.id,name:e.target.value})}>{OWNERS.map(n=><option key={n} value={n}>{n}</option>)}</select></div></div>
        <div className={styles.maintenanceInside}><div className={styles.maintenanceTitle}>MAINTENANCE &amp; COMPLIANCE</div><div className={styles.maintenanceGrid}>{([{key:"MOT",d:selected?.mot_due},{key:"Inspection",d:selected?.inspection_due},{key:"Service",d:selected?.service_due}] as const).map(x=><div key={x.key} className={x.d&&x.d<data.today?styles.overdueEvent:""}><small>{x.key}{x.d&&x.d<data.today?" · OVERDUE":""}</small><strong>{dgb(x.d||"")}</strong><button onClick={()=>selected&&openBook(selected,x.key)}>Book / view</button></div>)}</div></div>
       </div>
      </div>

      </div>
    <section className={`${styles.panel} ${styles.chatterPane}`}><div className={styles.chatterTop}><div className={styles.panelHeading}><div><h2>Communication history · All sources</h2></div><span className={styles.linkedCount}>{tickets.length} linked tickets</span></div><div className={styles.subscribers}><div className={styles.subscriberTop}><button type="button" className={styles.subscribersToggle} aria-expanded={showSubscribers} onClick={()=>setShowSubscribers(v=>!v)}><strong>Subscribers ({selectedContacts.length})</strong><span>{selectedContacts.length?selectedContacts.slice(0,2).map(c=>c.name).join(", ")+(selectedContacts.length>2?" + more":""):"No subscribers"}</span><em>{showSubscribers?"▴":"▾"}</em></button><button onClick={()=>setShowPeople(v=>!v)}>{showPeople?"Close Manage":"Manage"}</button></div>{showSubscribers&&<div className={styles.subscriberGroups}><div><small>INTERNAL</small><div>{selectedContacts.filter(c=>c.role==="internal").map(c=><span title={c.email} key={c.id} className={styles.personChip}>{c.name}</span>)}</div></div><div><small>EXTERNAL</small><div>{selectedContacts.filter(c=>c.role==="external").map(c=><span title={c.email} key={c.id} className={styles.externalChip}>{c.name}</span>)}</div></div></div>}</div>
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
    <div className={styles.activityToolbar}><div className={styles.filterBar}>{FILTERS.map(f=><button key={f.id} onClick={()=>setFilter(f.id)} className={filter===f.id?styles.filterActive:""}>{f.label}</button>)}</div><div className={styles.ticketFilter}><span>Ticket:</span>
      <button type="button" className={ticketFilter==="all"?styles.ticketActive:""} onClick={()=>setTicketFilter("all")}>All</button>
      <button type="button" className={ticketFilter==="vehicle-only"?styles.ticketActive:""} onClick={()=>setTicketFilter("vehicle-only")}>Vehicle</button>
      {tickets.map(t=><button type="button" key={t.id} title={t.title} className={ticketFilter===t.id?styles.ticketActive:""}
        aria-pressed={ticketFilter===t.id} onClick={()=>setTicketFilter(t.id)}>{t.id}</button>)}
      </div></div></div>
     <div className={styles.timeline} ref={timelineRef} key={`${selected?.id}-${filter}-${ticketFilter}-${clock}`}>{events.map(e=><MessageCard key={e.id} event={e}/>)}{events.length===0&&<div className={styles.emptyActivity}>No activity with these filters</div>}</div>
     <div className={styles.compose}><div className={styles.composeTabs}><button onClick={()=>setComposeKind("internal")} className={composeKind==="internal"?styles.composeActive:""}>Internal note</button><button onClick={()=>setComposeKind("email")} className={composeKind==="email"?styles.composeActive:""}>All subscribers</button><span>{session.liveEmail?"Live email enabled":"Email simulation"}</span></div>
      {composeKind==="email"&&<div className={styles.emailFields}><div className={styles.recipientSummary}><strong>To all vehicle subscribers ({selectedContacts.length})</strong><small>{selectedContacts.map(c=>c.email).join(", ") || "No subscribers — manage subscribers first"}</small></div><input aria-label="Email subject" placeholder="Subject" value={subject} onChange={e=>setSubject(e.target.value)} /></div>}
      <div className={styles.composeBottom}><textarea value={message} onChange={e=>setMessage(e.target.value)} placeholder={composeKind==="email"?"Write an email…":"Write an internal update…"}/><button aria-label="Save message" disabled={busy||!message.trim()||(composeKind==="email"&&selectedContacts.length===0)} onClick={post}>{busy?"…":"➤"}</button></div>
     </div>
    </section>
    {/* SECTION_WORKFLOW_MOVED */}
    <section className={styles.middlePane}>
      <div className={styles.workflow}>
       <div className={styles.workflowTopRow}><div className={styles.panelHeading}><h2>Repair workflow</h2><span>{doneStages}/{currentSteps.length} completed</span></div><div className={styles.workflowHeaderActions}><button type="button" className={styles.workflowToggle} aria-label={workflowExpanded?"Collapse workflow stages":"Expand workflow stages"} aria-expanded={workflowExpanded} onClick={()=>setWorkflowExpanded(v=>!v)}>{workflowExpanded?"Hide details −":"Show stages +"}</button></div></div>
       {tickets.length>1&&<nav className={styles.workflowTicketNav} aria-label="Repair ticket navigation">
        <span>Ticket</span><button type="button" aria-label="Previous ticket" onClick={()=>setTicketFilter(tickets[(ticketIndex-1+tickets.length)%tickets.length].id)}>‹</button>
        {tickets.map(t=><button key={t.id} type="button" className={t.id===primary?.id?styles.ticketActive:""} aria-pressed={t.id===primary?.id}
          title={`${t.title} · ${t.status}`} onClick={()=>setTicketFilter(t.id)}>{t.id}</button>)}
        <button type="button" aria-label="Next ticket" onClick={()=>setTicketFilter(tickets[(ticketIndex+1)%tickets.length].id)}>›</button>
      </nav>}
       <div className={styles.workflowSummary}>
        <div className={styles.workflowProgress} role="progressbar" aria-label="Workflow completion" aria-valuenow={doneStages} aria-valuemin={0} aria-valuemax={currentSteps.length||1}>{currentSteps.map(s=><span key={s.step_index} className={(s.status==="done"||s.status==="skipped")?styles.progressDone:s.status==="current"?styles.progressCurrent:""}/>)}</div>
        {currentStage?<button type="button" className={styles.currentStageButton} disabled={!canAdvanceStage} title="Complete the current workflow stage" onClick={()=>{if(selected&&primary&&canAdvanceStage)mutate("/checklists/advance",{vehicle_id:selected.id,ticket_id:primary.id})}}><span>Current: {currentStage.label}</span><strong>✓ Complete</strong></button>:<span className={styles.workflowCompleteLabel}>{currentSteps.length?"All stages completed":"No stages assigned"}</span>}
       </div>
       {workflowExpanded&&<div className={styles.scenarioRow}><label htmlFor="vor-scenario">Repair / service scenario</label><select id="vor-scenario" value={primary?.scenario||""} disabled={busy||!primary||primary.status!=="open"} onChange={e=>{if(!selected||!primary)return;const code=e.target.value;if(code===primary.scenario)return;if(!window.confirm(`Change workflow to ${SCENARIO_LABELS[code]||code}? Current stage progress for ${primary.id} will restart.`))return;mutate("/scenario",{vehicle_id:selected.id,ticket_id:primary.id,scenario:code})}}>{data.workflows.map(w=><option key={w.code} value={w.code}>{SCENARIO_LABELS[w.code]||w.name}</option>)}</select><small>{primary?.id}</small></div>}
       {workflowExpanded&&<ol className={styles.workflowStages} aria-label="Repair workflow stages">{currentSteps.map(s=>{
        const completed = s.status==="done";
        const skipped = s.status==="skipped";
        const active = s.status==="current";
        const opened = expandedStage===s.step_index || (expandedStage===null && active);
        const canComplete = active && !busy && !savingChecklist && checklistReady(s.step_index) && Boolean(selected) && primary?.status==="open";
        const items = stageList(s.step_index);
        const doneItems = items.filter(item=>checklist[`${s.step_index}:${item.key}`]?.checked).length;
        return <li key={`${primary?.id}-${s.step_index}`} className={completed||skipped?styles.stageDone:active?styles.stageCurrent:styles.stagePending}>
          <button type="button" className={styles.stageButton} aria-expanded={opened} aria-label={`${s.label}, ${completed?"completed":skipped?"not required":active?"in progress":"pending"}; ${opened?"collapse":"expand"} checklist`}
             onClick={()=>setExpandedStage(opened?-1:s.step_index)}>
            <span className={styles.stageMarker}>{completed?"✓":skipped?"N/R":s.step_index+1}</span>
            <span className={styles.stageLabel}>{s.label}</span>
            {completed&&<span className={styles.stageStateDone}>✓ Done</span>}
            {skipped&&<span className={styles.stageStateDone}>Not required</span>}
            {active&&<span className={styles.stageStateActive}>{doneItems}/{items.length} checks</span>}
            <span className={styles.stageChevron} aria-hidden="true">{opened?"⌃":"⌄"}</span>
          </button>
          {opened && <div className={styles.stageChecklist} aria-label={`Checklist for ${s.label}`}>
            {completed && doneItems===0 ? <p className={styles.historicStep}>Completed before checklist tracking was recorded.</p> : <>
              {items.length===0 && <p className={styles.historicStep}>No checklist configured for this stage.</p>}
              {items.map(item=><label className={styles.checklistEntry} key={item.key}>
                {item.type==="date" ? <>
                  <span>{item.label}{item.required===false?" (optional)":""}</span>
                  <input type="date" disabled={savingChecklist||busy||!active} value={checklist[`${s.step_index}:${item.key}`]?.value||""}
                    onChange={e=>void saveChecklist(s.step_index,item.key,Boolean(e.target.value),e.target.value||null)}/>
                </> : <>
                  <input type="checkbox" disabled={savingChecklist||busy||!active} checked={checklist[`${s.step_index}:${item.key}`]?.checked||false}
                    onChange={e=>void saveChecklist(s.step_index,item.key,e.target.checked)}/>
                  <span>{item.label}{item.required===false?" (optional)":""}</span>
                </>}
              </label>)}
            </>}
            {active && <div className={styles.stageFooter}>
              {!checklistReady(s.step_index)&&<span>Complete all mandatory checks to continue.</span>}
              <button type="button" className={styles.stageFinish} disabled={!canComplete}
                 onClick={()=>{if(canComplete&&selected&&primary)mutate("/checklists/advance",{vehicle_id:selected.id,ticket_id:primary.id})}}>
                 ✓ Finish stage
              </button>
            </div>}
          </div>}
        </li>;
       })}</ol>}
       {currentSteps.length===0&&<p className={styles.workflowEmpty}>No stages assigned to this ticket.</p>}
       {selected&&<OperationsPanel key={`${selected.id}-${primary?.id||"no-ticket"}`} vehicleId={selected.id} ticketId={primary?.id||null} onSaved={load}/>}
      </div>
    </section>
      </div>
  </main>}
  {bookingForm&&<div className={styles.modalBackdrop} role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setBookingForm(null)}}><form className={styles.bookModal} onSubmit={e=>{e.preventDefault();mutate("/bookings",{vehicle_id:bookingForm.vehicle.id,kind:bookingForm.kind,booked_date:bookingDate,garage:bookingGarage},()=>setBookingForm(null))}}><h2>Book {bookingForm.kind}</h2><p>{bookingForm.vehicle.registration} · {bookingForm.vehicle.model}</p><label>Date<input type="date" min={data.today} value={bookingDate} onChange={e=>setBookingDate(e.target.value)} required/></label><label>Garage<input value={bookingGarage} onChange={e=>setBookingGarage(e.target.value)} required/></label><div><button type="button" onClick={()=>setBookingForm(null)}>Cancel</button><button disabled={busy} type="submit">Save booking</button></div></form></div>}
 </div>;
}
