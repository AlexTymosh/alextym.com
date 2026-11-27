import { useEffect, useState } from "react";
import type { Card } from "./game-model.ru";
import { CardArtwork } from "./CardArtwork.ru";
import { EyeIcon } from "./GameIcons";
import styles from "./preferans-table.module.css";
import { WIDOW_SHOW_MS } from "./table-refinements";
export function WidowDisplay({cards,onReplay}:{cards:Card[];onReplay?:()=>void}) {
  const [automatic,setAutomatic]=useState(true);
  const [replay,setReplay]=useState(false);
  useEffect(()=>{const timer=setTimeout(()=>setAutomatic(false),WIDOW_SHOW_MS);return()=>clearTimeout(timer);},[]);
  const visible=automatic||replay;
  return <div className={styles.widow} data-widow-zone="true" aria-label="Прикуп" data-public-widow={visible?"true":"false"}>
    <div className={styles.widowCards}>{cards.map((card,i)=><span key={i} className={visible?styles.tableCard:styles.widowGhost}>{visible&&<CardArtwork card={card}/>}</span>)}</div>
    {!automatic&&<button type="button" className={styles.widowEye} aria-label={visible?"Скрыть прикуп":"Показать прикуп"} aria-expanded={visible} onClick={()=>{setReplay(v=>!v);if(onReplay&&!visible)onReplay();}}><EyeIcon/></button>}
  </div>;
}
