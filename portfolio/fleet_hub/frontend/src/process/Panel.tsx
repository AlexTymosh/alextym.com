"use client";

import {useRef,useState,type PointerEvent} from "react";
import styles from "./process.module.css";

type Lane = "driver" | "osd" | "fleet" | "garage";
type Step = {id:string;lane:Lane;x:number;title:string;detail:string;kind?:"gateway"|"end"};
const laneData:{id:Lane;name:string;subtitle:string;color:string;heading:string}[]=[
  {id:"driver",name:"DRIVER",subtitle:"Vehicle operator",color:"#E9EFF6",heading:"#65849D"},
  {id:"osd",name:"OSD / HOTH",subtitle:"Tickets, recovery & specialist repairs",color:"#F6ECEB",heading:"#AF7B79"},
  {id:"fleet",name:"PTS FLEET",subtitle:"Repair co-ordination & release",color:"#EBF3E9",heading:"#73976F"},
  {id:"garage",name:"GARAGE / SUPPLIER",subtitle:"External repair provider",color:"#F7F2E8",heading:"#AB9774"},
];
const laneY:Record<Lane,number>={driver:66,osd:169,fleet:272,garage:375};
const CARD_WIDTH=139;
const initialSteps:Step[]=[
  {id:"report",lane:"driver",x:170,title:"Report defect",detail:"Contact operations desk"},
  {id:"ticket",lane:"osd",x:330,title:"Log incident",detail:"Create HOTH ticket"},
  {id:"roadside",lane:"osd",x:495,title:"Roadside?",detail:"Yes / No",kind:"gateway"},
  {id:"recovery",lane:"osd",x:620,title:"Arrange recovery",detail:"Tow vehicle to garage"},
  {id:"received",lane:"garage",x:775,title:"Vehicle received",detail:"Continue defect process"},
  {id:"route",lane:"osd",x:818,title:"Defect type?",detail:"Standard / specialist",kind:"gateway"},
  {id:"specialist",lane:"osd",x:968,title:"Specialist repair",detail:"Tyres / windscreen"},
  {id:"standard",lane:"fleet",x:968,title:"Register Fleet case",detail:"Standard Defect"},
  {id:"garage",lane:"garage",x:1135,title:"Diagnose & repair",detail:"Quotation and work"},
  {id:"specialistDone",lane:"osd",x:1135,title:"Confirm specialist",detail:"Repair completion"},
  {id:"release",lane:"fleet",x:1302,title:"Release checks",detail:"Confirm roadworthiness"},
  {id:"close",lane:"osd",x:1461,title:"Close HOTH ticket",detail:"Notify OSD"},
  {id:"docs",lane:"fleet",x:1461,title:"Document follow-up",detail:"Collect repair records"},
  {id:"status",lane:"fleet",x:1620,title:"Fleet confirmation",detail:"Manual status update"},
  {id:"end",lane:"driver",x:1780,title:"Return to service",detail:"Vehicle back on road",kind:"end"},
];
const edges:[string,string,string?][]=[
  ["report","ticket"],["ticket","roadside"],["roadside","route","No"],["roadside","recovery","Yes"],
  ["recovery","received"],["received","route"],["route","standard","Standard"],["route","specialist","Tyres / glass"],
  ["standard","garage"],["garage","release"],["specialist","specialistDone"],["specialistDone","release"],
  ["release","close"],["release","docs"],["close","status"],["docs","status"],["status","end"],
];
function FlowChart(){
  const [steps,setSteps]=useState<Step[]>(initialSteps);
  const drag=useRef<{id:string;pointer:number;startX:number;initial:number}|null>(null);
  const svgRef=useRef<SVGSVGElement|null>(null);
  const position=(id:string)=>steps.find(s=>s.id===id)!;
  const move=(e:PointerEvent<SVGGElement>)=>{
    if(!drag.current||drag.current.pointer!==e.pointerId||!svgRef.current)return;
    const width=svgRef.current.getBoundingClientRect().width;
    const delta=(e.clientX-drag.current.startX)*1900/width;
    const x=Math.max(158,Math.min(1744,drag.current.initial+delta));
    const id=drag.current.id;
    setSteps(current=>current.map(s=>s.id===id?{...s,x}:s));
  };
  const finish=(e:PointerEvent<SVGGElement>)=>{
    if(drag.current?.pointer===e.pointerId){drag.current=null;if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId)}
  };
  return <div className={styles.diagramScroll} role="region" aria-label="Movable cross-functional swimlane diagram" tabIndex={0}>
    <svg ref={svgRef} className={styles.diagramSvg} viewBox="0 0 1900 504" role="img" aria-label="Proposed vehicle defect handling across Driver, OSD/HOTH, Fleet, and garage. Roadside recovery returns to repair workflow. Manual Fleet confirmation precedes return to service.">
      <defs><marker id="vor-to-be-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#556B76"/></marker></defs>
      <rect width="1900" height="504" fill="#fff" rx="9" />
      <text x="14" y="26" className={styles.svgPoolTitle}>VEHICLE DEFECT HANDLING · TO-BE</text>
      <text x="1880" y="26" textAnchor="end" className={styles.svgCaption}>Drag task cards horizontally to arrange the diagram · Reset layout to restore</text>
      {laneData.map(lane=><g key={lane.id}>
        <rect x="2" y={laneY[lane.id]} width="1895" height="102" fill={lane.color} stroke="#fff" strokeWidth="2"/>
        <rect x="2" y={laneY[lane.id]} width="145" height="102" fill={lane.heading}/>
        <text x="11" y={laneY[lane.id]+40} className={styles.svgLane}>{lane.name}</text>
        <text x="11" y={laneY[lane.id]+58} className={styles.svgLaneSub}>{lane.subtitle}</text>
      </g>)}
      {edges.map(([a,b,label])=>{
        const source=position(a),target=position(b);
        const sx=source.x+CARD_WIDTH,ex=target.x,sy=laneY[source.lane]+52,ey=laneY[target.lane]+52;
        const mx=sx+(ex-sx)/2;
        const d=(sy===ey)?`M${sx} ${sy} L${ex} ${ey}`:`M${sx} ${sy} H${mx} V${ey} H${ex}`;
        return <g key={`${a}-${b}`}><path d={d} className={styles.connector} markerEnd="url(#vor-to-be-arrow)"/>
          {label&&<g><rect x={mx-5} y={Math.min(sy,ey)-22} width={label.length*5.2+16} height="17" fill="#fff" rx="4"/><text x={mx} y={Math.min(sy,ey)-10} className={styles.svgEdgeLabel}>{label}</text></g>}
        </g>;
      })}
      {steps.map(step=>{
        const y=laneY[step.lane]+21;
        return <g key={step.id} className={styles.draggable} transform={`translate(${step.x},${y})`}
          onPointerDown={e=>{if(e.button!==0)return;drag.current={id:step.id,pointer:e.pointerId,startX:e.clientX,initial:step.x};e.currentTarget.setPointerCapture(e.pointerId)}}
          onPointerMove={move} onPointerUp={finish} onPointerCancel={finish}>
          <rect width={CARD_WIDTH} height="62" rx="6" fill="#fff" stroke={step.kind==="gateway"?"#BC9D64":"#AABCC0"} strokeWidth="1.5" />
          <text x="10" y="24" className={styles.svgTask}>{step.title}</text>
          <text x="10" y="44" className={styles.svgTaskDetail}>{step.detail}</text>
        </g>;
      })}
    </svg>
    <div className={styles.diagramToolbar}><span>Drag cards within their department lane. Arrows adjust automatically.</span><button type="button" onClick={()=>setSteps(initialSteps)}>Reset layout</button></div>
  </div>;
}
const informationSources=["Outlook mailboxes","Microsoft Teams groups and chats","Internal calendar","Partner calendars","Fleet system notes","HOTH notes","Multiple unversioned Excel files"];
const issues:[string,string][]=[
 ["No single source of truth","Operational information is spread across mailboxes, calendars, notes, Teams and spreadsheets."],
 ["No RACI matrix","Ownership and accountability are not defined consistently."],
 ["No documented process","Formal procedures and a reliable knowledge handover are not available."],
 ["Duplicated activity","Messages may be read repeatedly by several colleagues and tasks duplicated."],
 ["Version uncertainty","Multiple Excel copies make it difficult to identify an authoritative record."],
];
export default function ProcessPanel(){
 const [mode,setMode]=useState<"to-be"|"as-is">("to-be");
 return <section className={styles.page}>
  <div className={styles.header}><div><span className={styles.kicker}>PROCESS DESIGN · CROSS-FUNCTIONAL SWIMLANES</span><h1>Defect handling</h1><p>Proposed process and current operational observations.</p></div>
    <div className={styles.tabs} role="tablist"><button type="button" role="tab" aria-selected={mode==="to-be"} className={mode==="to-be"?styles.active:""} onClick={()=>setMode("to-be")}>TO-BE · Proposed</button><button type="button" role="tab" aria-selected={mode==="as-is"} className={mode==="as-is"?styles.active:""} onClick={()=>setMode("as-is")}>AS-IS · Observations</button></div></div>
  {mode==="to-be"?<><p className={styles.banner}>Pragmatic compromise within existing operational constraints. Further improvements are possible.</p><div className={styles.surface}><div className={styles.diagramTitle}><h2>Proposed vehicle defect process</h2><span>Compact swimlane map · movable task cards</span></div><FlowChart/><p className={styles.explanation}>Roadside recovery rejoins the same repair process. OSD/HOTH manages tickets, recovery and specialist tyre/windscreen repairs. Standard repairs pass through Fleet and the external garage. Only a separate manual Fleet confirmation changes the recorded vehicle status; the final outcome is return to service.</p></div></>:<>
    <p className={styles.bannerMuted}><strong>The AS-IS process has not been formally mapped.</strong> The observations below are not an approved current-state BPMN diagram.</p>
    <div className={styles.asIsGrid}><section className={styles.surface}><h2>Fragmented information sources</h2><p>There is no single source of truth for a vehicle case.</p><ul className={styles.sourceList}>{informationSources.map(s=><li key={s}>{s}</li>)}</ul></section><section className={styles.surface}><h2>Communication channels</h2><div className={styles.channelList}>{["Microsoft Teams","Email","Telephone"].map(x=><span key={x}>{x}</span>)}</div></section></div>
    <section className={styles.surface}><h2>Observed operational difficulties</h2><div className={styles.issues}>{issues.map(([title,detail])=><article key={title}><strong>{title}</strong><p>{detail}</p></article>)}</div></section>
  </>}
  <p className={styles.footer}>Synthetic process model for planning and discussion. No connection to external operational systems.</p>
 </section>;
}
