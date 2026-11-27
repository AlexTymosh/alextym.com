import { useLayoutEffect, useRef, type CSSProperties } from "react";
import { Notebook } from "./Notebook.ru";
import type { RoomView } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
import styles from "./sheet-tear.module.css";

export const SHEET_TEAR_MS=6800;
const pieces=[
  {clip:"polygon(0 0,48% 0,51% 16%,46% 32%,50% 49%,29% 46%,14% 52%,0 47%)",x:-22,y:-13,angle:-30},
  {clip:"polygon(48% 0,100% 0,100% 51%,77% 46%,65% 53%,50% 49%,46% 32%,51% 16%)",x:25,y:-14,angle:21},
  {clip:"polygon(0 47%,14% 52%,29% 46%,50% 49%,47% 65%,53% 80%,49% 100%,0 100%)",x:-18,y:17,angle:-22},
  {clip:"polygon(50% 49%,65% 53%,77% 46%,100% 51%,100% 100%,49% 100%,53% 80%,47% 65%)",x:21,y:19,angle:33},
];

/** Original cartoon character; all effects share a single local timeline. */
function Character(){return <svg className={styles.character} viewBox="0 0 120 174" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#382a29" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round">
  <ellipse cx="65" cy="165" rx="32" ry="5" fill="#0b171b" opacity=".24" stroke="none"/>
  <g className={styles.legBack}><path d="M66 111L81 111L85 142L91 153L79 159L67 143Z" fill="#536c88"/><path d="M79 154Q91 148 98 157L98 164H78Q75 160 79 154Z" fill="#292c38"/></g>
  <g className={styles.legFront}><path d="M48 111L65 113L61 145L56 157L44 153L46 139Z" fill="#7089a2"/><path d="M45 153Q53 150 58 157L58 164H33Q30 157 45 153Z" fill="#353945"/></g>
  <path d="M47 63Q63 57 78 66Q89 89 80 116Q63 125 43 115L41 86Z" fill="#bc553b"/><path d="M50 66L62 78L75 65" stroke="#f8d4ac" strokeWidth="4"/><path d="M43 108Q62 113 80 108" stroke="#8c382e"/>
  <path d="M55 53L55 65Q61 72 69 64L69 52" fill="#e9aa79"/>
  <path d="M43 19Q51 8 72 13Q88 19 87 37L82 54Q77 62 62 61Q47 59 43 49L35 43L37 35Z" fill="#f0b783"/>
  <path d="M43 36L32 39Q26 43 34 46L43 47" fill="#f0b783"/><path d="M43 20Q46 5 67 8Q80 8 89 22L83 36L75 31L71 23Q54 30 43 25Z" fill="#554037"/>
  <ellipse cx="46" cy="34" rx="8" ry="10" fill="#fffdf0"/><ellipse cx="61" cy="34" rx="8" ry="10" fill="#fffdf0"/><ellipse cx="43" cy="36" rx="2.6" ry="3.5" fill="#25272c" stroke="none"/><ellipse cx="58" cy="36" rx="2.6" ry="3.5" fill="#25272c" stroke="none"/>
  <path d="M39 24L52 28M55 28L66 23M44 52Q55 47 66 52" strokeWidth="3.4"/><path d="M76 43Q88 37 87 48Q83 54 77 50" fill="#e9aa79"/>
  <g className={styles.armBack}><path d="M76 70Q90 72 86 87L72 94L49 84L54 75L72 81Z" fill="#e9aa79"/><path d="M73 66Q85 63 89 76L81 85L72 79Z" fill="#ac4435"/><path d="M49 84Q42 88 38 81Q33 76 39 73L52 75Z" fill="#f0b783"/></g>
  <g className={styles.armFront}><path d="M48 70Q39 69 33 83L13 77L9 88L34 98Q43 99 55 81Z" fill="#f0b783"/><path d="M45 65Q55 65 57 77L49 89L37 81Z" fill="#c86648"/><path d="M14 77L6 73Q0 76 5 81L2 85Q5 92 15 88Z" fill="#f0b783"/></g>
</svg>;}

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
      const scale=el.offsetWidth?bounds.width/el.offsetWidth||1:1;
      el.style.setProperty("--paper-x",`${(p.left+p.width/2-bounds.left)/scale}px`);
      el.style.setProperty("--paper-y",`${(p.top+p.height/2-bounds.top)/scale}px`);
      el.style.setProperty("--paper-w",`${paper.offsetWidth}px`);
      el.style.setProperty("--avatar-x",`${(a.left+a.width/2-bounds.left)/scale}px`);
      el.style.setProperty("--avatar-y",`${(a.top+a.height*.7-bounds.top)/scale}px`);
      el.style.setProperty("--facing",a.left+a.width/2<p.left+p.width/2?"-1":"1");
    };
    fit();const observer=typeof ResizeObserver!=="undefined"?new ResizeObserver(fit):null;
    observer?.observe(table);return()=>observer?.disconnect();
  },[view.sheet_loser]);
  return <div ref={scene} className={styles.scene} aria-hidden="true" data-sheet-tear-scene="true" style={{"--scene-ms":`${SHEET_TEAR_MS}ms`} as CSSProperties}>
    <div className={styles.walker}><Character/></div>
    <div className={styles.paper} data-tear-intact="true"><Notebook view={view} profiles={profiles} miniature/></div>
    {pieces.map((piece,index)=><div key={index} className={styles.piece} data-tear-piece="true" style={{clipPath:piece.clip,"--dx":`${piece.x}px`,"--dy":`${piece.y}px`,"--angle":`${piece.angle}deg`} as CSSProperties}><Notebook view={view} profiles={profiles} miniature/></div>)}
    <svg className={styles.ball} data-tear-ball="true" viewBox="0 0 60 54"><path d="M5 22L13 8L25 4L38 7L53 16L57 30L47 46L32 51L15 45L4 35Z" fill="#f9edcc" stroke="#a59b7b" strokeWidth="2"/><path d="M13 8L22 18L38 7M22 18L18 32L4 35M22 18L35 26L53 16M35 26L47 46L18 32L32 51M18 32L35 26" fill="none" stroke="#bbb096" strokeWidth="1.7"/></svg>
  </div>;
}
