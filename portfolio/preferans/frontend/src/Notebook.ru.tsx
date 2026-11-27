import { useId, useState, type CSSProperties, type ReactNode } from "react";
import { notebookAngle, splitPlayerName } from "./table-pr20";
import { notebookName } from "./room-preparation";
import { bidLabel, type RoomView, type NotebookMark } from "./game-model.ru";
import { notebookAt } from "./notebook-history";
import { packNotebookRows, poolEntryText, notebookEntryLabel, vistEquation, type InkToken } from "./notebook-layout";
import { tableSeats, type SeatProfile } from "./table-model";
import { punchGeometry, type NotebookPunch } from "./notebook-punches";
import styles from "./preferans-notebook.module.css";

export function Notebook({view, profiles, miniature=false, title, sheetExit, onClose, closeDisabled=false, reviewAction, scoreAdjustment}: {view: RoomView; profiles: SeatProfile[] | null; miniature?:boolean; title?:string; sheetExit?:ReactNode; onClose?:()=>void; closeDisabled?:boolean; reviewAction?:ReactNode; scoreAdjustment?:ReactNode}) {
  const [orientation,setOrientation] = useState(0);
  const [stepIndex,setStepIndex] = useState<number|null>(null);
  const [zoom,setZoom] = useState(1);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const score = view.score;
  if (!score) return <p>Расчётов пока нет.</p>;
  const seats = tableSeats(view.my_seat);
  const steps = view.score_sheet?.steps ?? [];
  const cursor = miniature||stepIndex===null?steps.length:Math.min(stepIndex,steps.length);
  const past = cursor<steps.length;
  const history = past?notebookAt(view.score_sheet!,cursor):view.score_sheet;
  const step = steps[cursor-1];
  const name = (seat:number) => notebookName(profiles?.[seat],`Игрок ${seat+1}`);
  const cellMarks=new Map<number[],NotebookMark[]>();
  const cells=new Map<number[],{kind:"hill"|"pool"|"vist";seat:number;against?:number}>();
  const vals = (kind: "hill" | "pool" | "vist", seat: number, against?: number) => {
    const current = kind === "vist" ? score.vists[seat]?.[against!] ?? 0 : score[kind][seat] ?? 0;
    const values = kind === "vist" ? history?.vists[seat]?.[against!] : history?.[kind][seat];
    const result=values ?? (current ? [current] : []);
    cellMarks.set(result,(history?.marks??[]).filter(m=>m.field===kind&&m.seat===seat&&m.against===(against??null)));
    cells.set(result,{kind,seat,against});
    return result;
  };
  const fields = (["left", "right", "bottom"] as const).map(position => {
    const seat = seats[position];
    const left = (seat + 1) % 3, right = (seat + 2) % 3;
    return {position, seat, left, right, hill: vals("hill",seat), pool: vals("pool",seat), lv: vals("vist",seat,left), rv: vals("vist",seat,right)};
  });
  const final=past?undefined:view.final_settlement;
  const finalPunches=final?view.final_punches??[]:[];
  const distributed=final?view.final_hill_vists:undefined;
  const packed=new Map<number[],InkToken[][]>();
  for(const [values,cell] of Array.from(cells.entries())){
    const marks=cellMarks.get(values)??[];
    const tokens=values.map((n,i):InkToken=>{
      const mark=marks.find(m=>m.index===i);
      const label=cell.kind==="pool"?poolEntryText(values,i,score.target??20):String(n);
      return {label:notebookEntryLabel(label),manual:!!mark?.manual,latest:!!mark?.latest,underline:!!distributed&&cell.kind==="hill"&&i===values.length-1};
    });
    const rows=packNotebookRows(tokens,cell.kind==="hill"?232:176);
    if(distributed&&cell.kind==="vist"&&cell.against!==undefined){
      const before=score.vists[cell.seat][cell.against], extra=distributed[cell.against];
      if(before||extra) rows.push(vistEquation(before,extra));
    }
    packed.set(values,rows);
  }
  const maxRows=(kind:"hill"|"pool"|"vist")=>Math.max(1,...Array.from(cells.entries()).filter(([,c])=>c.kind===kind).map(([v])=>packed.get(v)!.length));
  const hillRows=maxRows("hill"), poolRows=maxRows("pool"), vistRows=maxRows("vist");
  const rowHeight=25;
  const outer=Math.max(100, 66+(vistRows-1)*rowHeight+(final?28:0));
  const inner=outer+Math.max(56,20+poolRows*rowHeight);
  const w=Math.max(578,2*inner+Math.max(288,242+(hillRows-1)*58)+(finalPunches.length?154:0),2*outer+440);
  const h=Math.max(w+22,2*(inner+160+hillRows*rowHeight));
  const cx=w/2,cy=h/2-55,innerY=h-inner-20,outerY=h-outer-24;
  const slope=(innerY-cy-21)/(cx-inner-43);
  const text=(v:number[],x:number,y:number,angle=0,extent=176)=>{
    const rows=packed.get(v)??[];
    const kind=cells.get(v)?.kind;
    const direction=kind==="vist"?1:-1;
    return <g transform={`translate(${x} ${y}) rotate(${angle})`}>{rows.map((row,index)=>{
      const widths=row.map(t=>t.label.length*9.5+(t.manual?112:0)+7);
      const indent=kind==="hill"?index*(angle===0?Math.ceil(rowHeight/slope)+2:angle===-90?Math.ceil(rowHeight*slope)+2:0):0;
      const available=kind==="hill"?Math.max(24,extent-(angle===0?2*indent:index*(Math.ceil(rowHeight*slope)+2))):extent;
      const scale=Math.min(1,available/Math.max(1,widths.reduce((a,b)=>a+b,0)));
      let offset=0;
      return <g key={index} transform={`translate(${indent} ${direction*index*rowHeight}) scale(${scale} 1)`}>{row.map((token,i)=>{
        const start=offset;offset+=widths[i];const labelWidth=Math.max(1,token.label.length*9.5);
        const color=token.latest?"#b51524":token.manual?"#87620b":undefined;
        return <g key={i} fill={color}><text x={start} y={0} textLength={labelWidth} lengthAdjust="spacingAndGlyphs">{token.label}</text>{token.manual&&<text x={start+labelWidth+3} y={0} fill="#87620b" fontSize="10" textLength="105" lengthAdjust="spacingAndGlyphs">ручная корректировка</text>}{token.underline&&<g stroke={color??"#20498f"} strokeWidth="1.2"><line x1={start} x2={start+labelWidth} y1="4" y2="4"/><line x1={start} x2={start+labelWidth} y1="7" y2="7"/></g>}</g>;
      })}</g>;
    })}</g>;
  };
  const left = fields[0], right = fields[1], bottom = fields[2];
  const topPunch=finalPunches.some(p=>p.from!==bottom.seat&&p.to!==bottom.seat);
  const nameTop=topPunch?99:16;
  const nameY = (cy-24+nameTop)/2;
  const nameExtent = Math.max(20,cy-24-nameTop-24);
  const sideName = (seat:number, x:number, rotation:number) => <text x={x} y={nameY} transform={`rotate(${rotation} ${x} ${nameY})`} textAnchor="middle" dominantBaseline="central" textLength={name(seat).length*12>nameExtent?nameExtent:undefined} lengthAdjust="spacingAndGlyphs">{name(seat)}</text>;
  const [first,rest] = splitPlayerName(name(bottom.seat));
  const angle=notebookAngle(miniature?0:orientation);
  const rotation=angle===-90?`translate(0 ${w}) rotate(-90)`:angle===90?`translate(${h} 0) rotate(90)`:undefined;
  const signed=(n:number)=>n>0?`+${n}`:n<0?`−${Math.abs(n)}`:"0";
  const circle=(seat:number,against:number,x:number,y:number,rotation=0)=>{
    if(!final)return null;
    const amount=signed(final.pairs[seat][against]);
    return <g data-final-pair={`${seat}:${against}`} transform={`translate(${x} ${y}) rotate(${rotation})`}>
      <ellipse rx={Math.max(22,amount.length*5.8+8)} ry="14" stroke="#b51524" strokeWidth="2" fill="#fbf9ee"/>
      <text fill="#b51524" fontSize="17" textAnchor="middle" dominantBaseline="central">{amount}</text>
    </g>;
  };
  const total=(seat:number,x:number,y:number,rotation=0)=>{
    if(!final)return null;
    const amount=signed(final.net[seat]);
    const pair=final.pairs[seat].filter((_,i)=>i!==seat);
    return <g data-final-net={seat} transform={`translate(${x} ${y}) rotate(${rotation})`}><ellipse rx={Math.max(30,amount.length*7.8+10)} ry="18" fill="#fbf9ee" stroke="#b51524" strokeWidth="2.4"/><text fill="#b51524" fontSize="23.8" fontWeight="bold" textAnchor="middle" dominantBaseline="central">{amount}</text>{distributed&&<text y="35" fill="#b51524" fontSize="12" textAnchor="middle">{`${signed(pair[0])} ${signed(pair[1])} = ${amount}`}</text>}</g>;
  };
  const punchWord=(n:number)=>n%100>=11&&n%100<=14?"УДАРОВ":n%10===1?"УДАР":n%10>=2&&n%10<=4?"УДАРА":"УДАРОВ";
  const bareWord=(n:number)=>n%100!==11&&n%10===1?"ГОЛЫЙ":"ГОЛЫХ";
  const punchBadge=(p:NotebookPunch)=>{
    const {center,start,end}=punchGeometry(p,seats,w,cy,inner,innerY);
    const lines=p.bare&&p.ordinary?[`${p.bare} ${bareWord(p.bare)}`,`${p.ordinary} ${punchWord(p.ordinary)}`]:p.bare?[String(p.bare),bareWord(p.bare)]:[String(p.ordinary),punchWord(p.ordinary)];
    const counts=[p.bare?`${p.bare} ${bareWord(p.bare).toLowerCase()} ${punchWord(p.bare).toLowerCase()}`:"",p.ordinary?`${p.ordinary} ${punchWord(p.ordinary).toLowerCase()}`:""].filter(Boolean).join(", ");
    const label=`${name(p.from)} → ${name(p.to)}: ${counts}`;
    return <g key={`${p.from}:${p.to}`} data-punch-from={p.from} data-punch-to={p.to} aria-label={label}>
      <title>{label}</title>
      <path d={`M${start.x} ${start.y} L${end.x} ${end.y}`} stroke="#b51524" strokeWidth="2.4" fill="none" markerEnd={`url(#punch-arrow-${id})`}/>
      <circle cx={center.x} cy={center.y} r="37" fill="#b51524" fillOpacity="0.8" stroke="#fbf9ee" strokeWidth="1.5"/>
      {lines.map((line,i)=>{
        const size=i===0&&!(p.bare&&p.ordinary)?21:12;
        return <text key={i} x={center.x} y={center.y+(i===0?-8:11)} dominantBaseline="central" textAnchor="middle" fill="#fff" fontWeight="700" fontStyle="normal" fontSize={size} textLength={line.length*size*.7>51?51:undefined} lengthAdjust="spacingAndGlyphs">{line}</text>;
      })}
    </g>;
  };
  const Wrapper=miniature?"span":"div";
  return <Wrapper className={miniature?styles.miniature:styles.wrap} style={{"--paper-ratio":(angle?h:w)/(angle?w:h)} as CSSProperties} aria-label={miniature?undefined:"Пулька в клетку"} aria-hidden={miniature?true:undefined}>
    {!miniature&&<div className={styles.paperToolbar}>
      <div className={styles.paperExit}>{!past&&sheetExit}</div>
      <div className={styles.rotateControls}><button type="button" aria-label="Повернуть к левому игроку" onClick={()=>setOrientation(n=>(n+1)%3)}>↶</button><button type="button" aria-label="Моя сторона" onClick={()=>setOrientation(0)}>Моя сторона</button><button type="button" aria-label="Повернуть к правому игроку" onClick={()=>setOrientation(n=>(n+2)%3)}>↷</button></div>
      <div className={styles.zoomControls} aria-label="Масштаб пульки"><button type="button" aria-label="Уменьшить пульку" disabled={zoom<=0.5} onClick={()=>setZoom(z=>Math.max(0.5,z-0.25))}>−</button><button type="button" aria-label="Исходный масштаб" onClick={()=>setZoom(1)}>{Math.round(zoom*100)}%</button><button type="button" aria-label="Увеличить пульку" disabled={zoom>=4} onClick={()=>setZoom(z=>Math.min(4,z+0.25))}>+</button></div>
      {onClose&&<button type="button" className={styles.paperClose} aria-label="Закрыть пульку" title="Закрыть пульку" disabled={closeDisabled} onClick={onClose}>×</button>}
    </div>}
    {!miniature&&title&&<p className={styles.paperTitle}>{title}</p>}
    {!miniature&&!past&&reviewAction&&<div className={styles.reviewAction}>{reviewAction}</div>}
    {!miniature&&steps.length>0&&<div className={styles.historyNav} aria-label="История записей">
      <div><button type="button" aria-label="Предыдущая запись" disabled={cursor===0} onClick={()=>setStepIndex(cursor-1)}>←</button><strong>Запись {cursor} / {steps.length}</strong><button type="button" aria-label="Следующая запись" disabled={cursor===steps.length} onClick={()=>setStepIndex(cursor+1===steps.length?null:cursor+1)}>→</button><button type="button" onClick={()=>setStepIndex(null)} disabled={!past}>Последняя</button></div>
      <p>{step?step.kind==="manual"?"Ручная корректировка":step.kind==="penalty"?"Штраф":step.passout?`Распасы ${step.passout}`:step.contract&&step.declarer!=null?`${name(step.declarer)} · ${bidLabel(step.contract)}`:"Раздача (контракт не сохранён)":"Начало записей"}</p>
      {step&&<ul>{step.entries.map((e,i)=><li key={i}>{name(e.seat)} · {e.field==="hill"?"Гора":e.field==="pool"?"Пуля":`Висты на ${name(e.against!)}`} {signed(e.delta)}</li>)}</ul>}
    </div>}
    {!miniature&&!past&&scoreAdjustment&&<div className={styles.accountingActions}>{scoreAdjustment}</div>}
    <span className={miniature?styles.miniatureBody:styles.paperBody}>
    {!miniature&&<span className={styles.scissors} aria-hidden="true">✁</span>}
    <span className={miniature?styles.miniatureCanvas:styles.paperViewport} data-zoomed={!miniature&&zoom!==1?"true":undefined} style={{"--paper-zoom":miniature?1:zoom} as CSSProperties}>
    <svg viewBox={`0 0 ${angle?h:w} ${angle?w:h}`} className={styles.paper} role="img" aria-label="Рукописная пулька">
      <defs><pattern id={`grid-${id}`} width="16" height="16" patternUnits="userSpaceOnUse"><path d="M16 0H0V16" fill="none" stroke="#b4ccdb" strokeWidth=".65"/></pattern>{finalPunches.length>0&&<marker id={`punch-arrow-${id}`} markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L10 5.5L0 11Z" fill="#b51524"/></marker>}</defs>
      <g transform={rotation}><rect width={w} height={h} fill="#fbf9ee"/><rect width={w} height={h} fill={`url(#grid-${id})`}/>
      <g stroke="#28509a" strokeWidth="2" fill="none" strokeLinejoin="round">
        <path d={`M${cx} 16V${cy-24} M${cx-43} ${cy+21} L${inner} ${innerY} L${outer} ${outerY} L0 ${h} M${cx+43} ${cy+21} L${w-inner} ${innerY} L${w-outer} ${outerY} L${w} ${h} M${inner} 16V${innerY}H${w-inner}V16 M${outer} 16V${outerY}H${w-outer}V16 M0 ${cy}H${outer} M${w-outer} ${cy}H${w} M${cx} ${outerY}V${h}`}/>
        <path d={`M${cx-51} ${cy} C${cx-52} ${cy-34} ${cx+47} ${cy-34} ${cx+51} ${cy-2} C${cx+56} ${cy+32} ${cx-48} ${cy+34} ${cx-51} ${cy} Z`}/>
      </g>
      <g className={styles.ink}>
        <text x={cx} y={cy+9} textAnchor="middle" fontSize="28">{score.target??20}</text>
        <g data-score-seat={bottom.seat} data-score-position="bottom"><text x={cx} y={cy+53} textAnchor="middle"><tspan x={cx}>{first}</tspan>{rest&&<tspan x={cx} dy="1.2em">{rest}</tspan>}</text>{text(bottom.hill,inner+24,innerY-12,0,Math.min(232,w-2*inner-48))}{text(bottom.pool,outer+48,outerY-10)}{text(bottom.lv,outer+12,outerY+34)}{text(bottom.rv,cx+24,outerY+34)}{total(bottom.seat,cx,cy+(rest?103:82))}{circle(bottom.seat,bottom.left,(outer+cx)/2,h-25)}{circle(bottom.seat,bottom.right,(w-outer+cx)/2,h-25)}</g>
        <g data-score-seat={left.seat} data-score-position="left">{sideName(left.seat,cx-18,90)}{text(left.hill,inner+11,20,90,Math.min(232,innerY-Math.ceil(11*slope)-36))}{text(left.pool,outer+11,24,90)}{text(left.rv,outer-18,cy+22,90,outerY-(cy+22)-15)}{text(left.lv,outer-18,24,90,cy-42)}{total(left.seat,cx-49,nameY,90)}{circle(left.seat,left.left,25,cy/2,90)}{circle(left.seat,left.right,25,(cy+outerY)/2,90)}</g>
        <g data-score-seat={right.seat} data-score-position="right">{sideName(right.seat,cx+18,-90)}{text(right.hill,w-inner-11,innerY-Math.ceil(11*slope)-14,-90,Math.min(232,innerY-Math.ceil(11*slope)-36))}{text(right.pool,w-outer-11,outerY-30,-90)}{text(right.rv,w-outer+18,cy-22,-90,cy-42)}{text(right.lv,w-outer+18,outerY-15,-90,outerY-cy-35)}{total(right.seat,cx+49,nameY,-90)}{circle(right.seat,right.right,w-25,cy/2,-90)}{circle(right.seat,right.left,w-25,(cy+outerY)/2,-90)}</g>
        {finalPunches.map(punchBadge)}
      </g>
    </g></svg>
    </span>
    </span>
    {!miniature&&history?.exact===false && <p className={styles.notice}>Для старых исправлений порядок записей не сохранён. Показаны точные итоговые значения.</p>}
  </Wrapper>;
}
