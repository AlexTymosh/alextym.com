import { CardArtwork } from "./CardArtwork.ru";
import type { RoomView, CommandAction } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
import styles from "./preferans-table.module.css";

export function MisereOfferPanel({view,profiles,busy,command}:{view:RoomView;profiles:SeatProfile[]|null;busy:boolean;command:(action:CommandAction,args?:Record<string,unknown>)=>void}) {
  if(view.phase!=="misere_offer"||!view.misere_offer||view.declarer==null||view.my_seat===null)return null;
  const name=(seat:number)=>profiles?.[seat]?.name||`Игрок ${seat+1}`;
  const declarer=name(view.declarer);
  const cards=view.my_seat===view.declarer?view.hand??[]:view.open_hands?.find(hand=>hand.seat===view.declarer)?.cards??[];
  const waiting=[0,1,2].filter(seat=>seat!==view.declarer&&!view.misere_offer!.approved.includes(seat));
  return <section className={styles.claimPanel} role="region" aria-label="Предложение сыгранного мизера">
    <strong>{declarer} · предложение сыгранного мизера</strong>
    <div className={styles.claimCards}>{cards.map(card=><span key={`${card.suit}${card.rank}`}><CardArtwork card={card}/></span>)}</div>
    {view.misere_offer.can_vote?<div className={styles.claimVotes}>
      <button type="button" disabled={busy||!!view.controls?.paused||!!view.controls?.undo} onClick={()=>command("misere_vote",{approve:true})}>Согласен, что {declarer} сыграл мизер</button>
      <button type="button" disabled={busy||!!view.controls?.paused||!!view.controls?.undo} onClick={()=>command("misere_vote",{approve:false})}>Да хрен там, играем!!!</button>
    </div>:<p>Ожидаем: {waiting.map(name).join(", ")}</p>}
  </section>;
}
