import {useEffect,useLayoutEffect,useRef,useState,type CSSProperties} from "react";
import {CardArtwork} from "./CardArtwork.ru";
import {seatPosition} from "./table-model";
import type {RoomView} from "./game-model.ru";
import {GAG_FAKE_MS,GAG_TOTAL_MS,GAG_MISSING_MS,GAG_FOUND_MS,GAG_RETURN_MS,HIDE_DURATION_MS,gagPhase} from "./gag-model";
import styles from "./preferans-table.module.css";

// The only clock is a local presentation clock, synchronized to the server offset.
export function useDiscardScene(view:RoomView|null,serverNow:()=>number) {
  const [at,setAt]=useState(()=>serverNow());
  const hiddenAt=view?.hidden_discard?.at_ms;
  const redealAt=view?.redeal_gag?.at_ms;
  useEffect(()=>{
    const boundaries=[...(hiddenAt===undefined?[]:[hiddenAt+HIDE_DURATION_MS]),...(redealAt===undefined?[]:[redealAt+GAG_MISSING_MS,redealAt+GAG_FOUND_MS,redealAt+GAG_RETURN_MS,redealAt+GAG_FAKE_MS,redealAt+GAG_TOTAL_MS])].sort((a,b)=>a-b);
    if(!boundaries.length)return;
    let id:ReturnType<typeof setTimeout>;
    const tick=()=>{
      const next=serverNow();setAt(next);
      const boundary=boundaries.find(t=>t>next);
      if(boundary!==undefined)id=setTimeout(tick,Math.max(1,boundary-next));
    };
    id=setTimeout(tick,0);
    return()=>clearTimeout(id);
  },[hiddenAt,redealAt,serverNow]);
  return {now:at,phase:gagPhase(view?.redeal_gag,at),hide:Boolean(view?.hidden_discard&&at<view.hidden_discard.at_ms+HIDE_DURATION_MS)};
}
const destination={left:[16,29],right:[84,29],bottom:[57,84]} as const;
export function HiddenDiscardScene({view,now,hide,phase,name,serverNow}:{serverNow:()=>number;view:RoomView;now:number;hide:boolean;phase:"fake"|"deal"|null;name:(seat:number)=>string}) {
  const marker=phase==="fake"?view.redeal_gag:hide?view.hidden_discard:undefined;
  const [initial]=useState(()=>marker?Math.max(0,serverNow()-marker.at_ms):0);
  const scene=useRef<HTMLDivElement>(null);
  useLayoutEffect(()=>{
    const node=scene.current,table=node?.closest<HTMLElement>("[data-table-view]");
    if(!node||!table)return;
    const fit=()=>{
      const bounds=node.getBoundingClientRect();
      if(!bounds.width||!bounds.height)return;
      const set=(name:string,element:Element|null)=>{
        if(!element)return;
        const r=element.getBoundingClientRect();
        node.style.setProperty(`--${name}-x`,`${(r.left+r.width/2-bounds.left)/bounds.width*100}%`);
        node.style.setProperty(`--${name}-y`,`${(r.top+r.height/2-bounds.top)/bounds.height*100}%`);
        node.style.setProperty(`--${name}-step`,`${Math.min(2.3,r.width/10/bounds.width*100)}%`);
        node.style.setProperty(`--${name}-w`,`${r.width/bounds.width*100}%`);
        node.style.setProperty(`--${name}-h`,`${r.height/bounds.height*100}%`);
      };
      set("paper",table.querySelector("[data-paper-miniature]"));
      set("left",table.querySelector(`[data-position="left"] .${styles.opponentHand}`)??table.querySelector('[data-position="left"]'));
      set("right",table.querySelector(`[data-position="right"] .${styles.opponentHand}`)??table.querySelector('[data-position="right"]'));
      set("bottom",table.querySelector("[data-own-hand]"));
    };
    fit();table.style.setProperty("--gag-paper-offset",`${-initial}ms`);
    const observer=typeof ResizeObserver!=="undefined"?new ResizeObserver(fit):null;
    observer?.observe(table);
    return()=>{observer?.disconnect();table.style.removeProperty("--gag-paper-offset");};
  },[initial]);
  if(!marker)return null;
  const elapsed=Math.max(0,now-marker.at_ms);
  const pos=seatPosition(view.my_seat,marker.seat)??"bottom";
  const [x,y]=destination[pos];
  if(phase!=="fake")return <div ref={scene} className={styles.gagScene} aria-hidden="true">
    {[0,1].map(i=><span key={i} className={styles.gagHideCard} style={{"--from-x":`calc(var(--${pos}-x,${x}%) + ${i*2}%)`,"--from-y":`var(--${pos}-y,${y}%)`,"--gag-offset":`${-initial}ms`} as CSSProperties}><CardArtwork decorative/></span>)}
  </div>;
  return <div ref={scene} className={styles.gagScene} data-redeal-stage={elapsed<GAG_MISSING_MS?"deal":elapsed<GAG_FOUND_MS?"missing":elapsed<GAG_RETURN_MS?"found":"return"}>
    {[0,1].map(i=><span key={`found:${i}`} aria-hidden="true" className={styles.gagFoundCard} style={{"--gag-offset":`${-initial}ms`,"--found-offset":`${i*2.0}%`} as CSSProperties}><CardArtwork decorative/></span>)}
    {elapsed>=GAG_MISSING_MS&&elapsed<GAG_FOUND_MS&&<strong className={styles.gagMessage} role="status">Двух карт не хватает! {name(marker.seat)} ты задолбал, куда ты карты спрятал?!</strong>}
    {elapsed>=GAG_FOUND_MS&&elapsed<GAG_RETURN_MS&&<div className={styles.gagFoundHint}><svg viewBox="0 0 64 34" width="64" height="34" aria-hidden="true"><path d="M60 5Q28 -2 7 26M7 26L11 13M7 26L20 26" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg><strong>Вот они!</strong></div>}
    {elapsed>=GAG_RETURN_MS&&elapsed<GAG_FAKE_MS&&<strong className={styles.gagMessage}>Пересдаём!</strong>}
  </div>;
}
