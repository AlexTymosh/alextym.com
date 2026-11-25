import { useId } from "react";
import type { RoomView } from "./game-model.ru";
import { tableSeats, type SeatProfile } from "./table-model";
import styles from "./preferans-notebook.module.css";

export function Notebook({view, profiles}: {view: RoomView; profiles: SeatProfile[] | null}) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const score = view.score;
  if (!score) return <p>Расчётов пока нет.</p>;
  const seats = tableSeats(view.my_seat);
  const history = view.score_sheet;
  const name = (seat:number) => profiles?.[seat]?.name || `Игрок ${seat+1}`;
  const vals = (kind: "hill" | "pool" | "vist", seat: number, against?: number) => {
    const current = kind === "vist" ? score.vists[seat]?.[against!] ?? 0 : score[kind][seat] ?? 0;
    const values = kind === "vist" ? history?.vists[seat]?.[against!] : history?.[kind][seat];
    return values ?? (current ? [current] : []);
  };
  const fields = (["left", "right", "bottom"] as const).map(position => {
    const seat = seats[position];
    const left = (seat + 1) % 3, right = (seat + 2) % 3;
    return {position, seat, left, right, hill: vals("hill",seat), pool: vals("pool",seat), lv: vals("vist",seat,left), rv: vals("vist",seat,right)};
  });
  // Grow the entire drawing, not the font: long-running games retain every entry.
  const maxChars = Math.max(0, ...fields.flatMap(f => [f.hill,f.pool,f.lv,f.rv].map(v => v.map(n=>`. ${n}`).join(" ").length)));
  const extra = Math.max(0, maxChars * 10 - 175);
  const w = 578 + extra * 2, h = 600 + extra * 2, cx = w/2, cy = h/2 - 55;
  const inner = 142, outer = 88, innerY = h-176, outerY = h-124;
  const rows = (v:number[]) => v.map(n=>`. ${n}`).join(" ");
  const text = (v:number[], x:number,y:number, angle=0) => <text x={x} y={y} transform={`rotate(${angle} ${x} ${y})`}>{rows(v)}</text>;
  const left = fields[0], right = fields[1], bottom = fields[2];
  const nameY = (cy-24+16)/2;
  const nameExtent = Math.max(20,cy-64);
  const sideName = (seat:number, x:number, rotation:number) => <text x={x} y={nameY} transform={`rotate(${rotation} ${x} ${nameY})`} textAnchor="middle" dominantBaseline="central" textLength={name(seat).length*12>nameExtent?nameExtent:undefined} lengthAdjust="spacingAndGlyphs">{name(seat)}</text>;
  return <div className={styles.wrap} aria-label="Пулька в клетку">
    <svg viewBox={`0 0 ${w} ${h}`} className={styles.paper} style={{minWidth:`${Math.max(328,w*.5355)}px`}} role="img" aria-label="Рукописная пулька">
      <defs><pattern id={`grid-${id}`} width="16" height="16" patternUnits="userSpaceOnUse"><path d="M16 0H0V16" fill="none" stroke="#b4ccdb" strokeWidth=".65"/></pattern></defs>
      <rect width={w} height={h} fill="#fbf9ee"/><rect width={w} height={h} fill={`url(#grid-${id})`}/>
      <g stroke="#28509a" strokeWidth="2" fill="none" strokeLinejoin="round">
        <path d={`M${cx} 16V${cy-24} M${cx-51} ${cy+24} L${inner} ${innerY} L${outer} ${outerY} L0 ${outerY+88} M${cx+51} ${cy+24} L${w-inner} ${innerY} L${w-outer} ${outerY} L${w} ${outerY+88} M${inner} 16V${innerY}H${w-inner}V16 M${outer} 16V${outerY}H${w-outer}V16 M0 ${cy}H${outer} M${w-outer} ${cy}H${w} M${cx} ${outerY}V${h}`}/>
        <rect x={cx-51} y={cy-24} width="102" height="48"/>
      </g>
      <g className={styles.ink}>
        <text x={cx} y={cy+9} textAnchor="middle" fontSize="28">{score.target??20}</text>
        <g data-score-seat={bottom.seat} data-score-position="bottom"><text x={cx} y={cy+53} textAnchor="middle">{name(bottom.seat)}</text>{text(bottom.hill,inner+50,innerY-12)}{text(bottom.pool,outer+48,outerY-10)}{text(bottom.lv,outer+12,outerY+34)}{text(bottom.rv,cx+24,outerY+34)}</g>
        <g data-score-seat={left.seat} data-score-position="left">{sideName(left.seat,cx-18,90)}{text(left.hill,inner+11,24,90)}{text(left.pool,outer+11,24,90)}{text(left.rv,outer-35,cy+22,90)}{text(left.lv,outer-35,24,90)}</g>
        <g data-score-seat={right.seat} data-score-position="right">{sideName(right.seat,cx+18,-90)}{text(right.hill,w-inner-11,innerY-30,-90)}{text(right.pool,w-outer-11,outerY-30,-90)}{text(right.rv,w-outer+35,cy-22,-90)}{text(right.lv,w-outer+35,h-40,-90)}</g>
      </g>
    </svg>
    {history?.exact===false && <p className={styles.notice}>Для старых исправлений порядок записей не сохранён. Показаны точные итоговые значения.</p>}
  </div>;
}
