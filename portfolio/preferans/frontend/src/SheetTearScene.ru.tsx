import { useLayoutEffect, useRef, type CSSProperties } from "react";
import { Notebook } from "./Notebook.ru";
import type { RoomView } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
import styles from "./preferans-table.module.css";

export const SHEET_TEAR_MS=3800;
// Complementary zigzag edges keep the pieces of the original drawing intact before tearing.
const pieces=[
  {clip:"polygon(0 0,48% 0,51% 16%,46% 32%,50% 49%,29% 46%,14% 52%,0 47%)",x:-18,y:-14,angle:-30},
  {clip:"polygon(48% 0,100% 0,100% 51%,77% 46%,65% 53%,50% 49%,46% 32%,51% 16%)",x:20,y:-15,angle:21},
  {clip:"polygon(0 47%,14% 52%,29% 46%,50% 49%,47% 65%,53% 80%,49% 100%,0 100%)",x:-16,y:19,angle:-22},
  {clip:"polygon(50% 49%,65% 53%,77% 46%,100% 51%,100% 100%,49% 100%,53% 80%,47% 65%)",x:22,y:18,angle:33},
];

/** Rendered only after an authoritative technical defeat. No commands or score changes. */
export function SheetTearScene({view,profiles}:{view:RoomView;profiles:SeatProfile[]|null}) {
  const scene=useRef<HTMLDivElement>(null);
  useLayoutEffect(()=>{
    const el=scene.current,table=el?.closest<HTMLElement>("[data-table-view]");
    if(!el||!table)return;
    const fit=()=>{
      const bounds=el.getBoundingClientRect();
      const paper=table.querySelector<HTMLElement>("[data-paper-miniature]");
      const avatar=table.querySelector<HTMLElement>(`[data-seat="${view.sheet_loser}"] [data-turn]`);
      if(!bounds.width||!bounds.height||!paper||!avatar)return;
      const p=paper.getBoundingClientRect(),a=avatar.getBoundingClientRect();
      el.style.setProperty("--tear-x",`${p.left+p.width/2-bounds.left}px`);
      el.style.setProperty("--tear-y",`${p.top+p.height/2-bounds.top}px`);
      el.style.setProperty("--tear-w",`${paper.offsetWidth}px`);
      el.style.setProperty("--tear-from-x",`${a.left+a.width/2-bounds.left}px`);
      el.style.setProperty("--tear-from-y",`${a.top+a.height*.77-bounds.top}px`);
    };
    fit();
    const observer=typeof ResizeObserver!=="undefined"?new ResizeObserver(fit):null;
    observer?.observe(table);
    return()=>observer?.disconnect();
  },[view.sheet_loser]);
  return <div ref={scene} className={styles.sheetTearScene} aria-hidden="true" style={{"--tear-x":"10%","--tear-y":"62%","--tear-w":"10cqw","--tear-from-x":"50%","--tear-from-y":"80%"} as CSSProperties}>
    {pieces.map((piece,index)=><div key={index} className={styles.tearPiece} style={{clipPath:piece.clip,"--tear-dx":`${piece.x}px`,"--tear-dy":`${piece.y}px`,"--tear-angle":`${piece.angle}deg`} as CSSProperties}><Notebook view={view} profiles={profiles} miniature/></div>)}
    <svg className={styles.tearWalker} viewBox="0 0 48 70" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="24" cy="10" r="7" fill="currentColor" stroke="none"/>
      <path d="M24 22V43M24 25L10 35M24 25L39 29"/>
      <g className={styles.walkerLeg}><path d="M24 43L14 56L9 65"/></g>
      <g className={styles.walkerLeg}><path d="M24 43L34 56L39 65"/></g>
    </svg>
  </div>;
}
