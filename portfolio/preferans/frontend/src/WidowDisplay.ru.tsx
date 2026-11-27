import { useEffect, useState } from "react";
import type { Card } from "./game-model.ru";
import { CardArtwork } from "./CardArtwork.ru";
import { EyeIcon } from "./GameIcons";
import styles from "./preferans-table.module.css";
import { WIDOW_SHOW_MS } from "./table-refinements";

/** Only receives already-public cards. The parent unmounts it at the first play. */
export function WidowDisplay({cards}:{cards:Card[]}) {
  const [automatic,setAutomatic]=useState(true);
  const [held,setHeld]=useState(false);
  useEffect(()=>{
    const timer=setTimeout(()=>setAutomatic(false),WIDOW_SHOW_MS);
    const release=()=>setHeld(false);
    window.addEventListener("blur",release);
    document.addEventListener("visibilitychange",release);
    return()=>{clearTimeout(timer);window.removeEventListener("blur",release);document.removeEventListener("visibilitychange",release);};
  },[]);
  const visible=automatic||held;
  return <div className={styles.widow} data-widow-zone="true" aria-label="Прикуп" data-public-widow={visible?"true":"false"}>
    <div className={styles.widowCards}>{cards.map((card,i)=><span key={i} className={visible?styles.tableCard:styles.widowGhost}>{visible&&<CardArtwork card={card}/>}</span>)}</div>
    {!automatic&&<button type="button" className={styles.widowEye} aria-pressed={held}
      onPointerDown={event=>{if(event.button!==0)return;event.currentTarget.setPointerCapture(event.pointerId);setHeld(true);}}
      onPointerUp={()=>setHeld(false)} onPointerCancel={()=>setHeld(false)} onLostPointerCapture={()=>setHeld(false)} onBlur={()=>setHeld(false)}
      onKeyDown={event=>{if(event.key===" "||event.key==="Enter"){event.preventDefault();setHeld(true);}}}
      onKeyUp={event=>{if(event.key===" "||event.key==="Enter"){event.preventDefault();setHeld(false);}}}>
      <EyeIcon/><span>покажи что там было в прикупе</span>
    </button>}
  </div>;
}
