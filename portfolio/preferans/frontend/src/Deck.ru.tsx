import type { DragEvent } from "react";
import { CardArtwork } from "./CardArtwork.ru";
import styles from "./preferans-table.module.css";
export function Deck({enabled, canDeal, start, drag, end}: {enabled:boolean; canDeal:boolean; start:()=>void; drag:(e:DragEvent<HTMLButtonElement>)=>void; end:()=>void}) {
  return <button type="button" className={styles.deck} data-pointer-drag="deck" aria-label={canDeal?"Колода: раздать карты":enabled?"Колода: передать сдачу":"Колода"} title={enabled?"Перетащи в центр для раздачи или к сопернику для передачи сдачи":"Ожидаем раздачу"} draggable={enabled} disabled={!enabled} onClick={enabled&&canDeal?start:undefined} onDragStart={drag} onDragEnd={end}>
    <span className={styles.deckStack} data-deck-collect-target="true"><CardArtwork decorative/></span><span>{enabled&&!canDeal?"Передать колоду":"Колода"}</span>
  </button>;
}
