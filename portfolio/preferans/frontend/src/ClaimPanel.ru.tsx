import { CardArtwork } from "./CardArtwork.ru";
import { claimVoteLabels } from "./claim-copy.ru";
import type { CommandAction, RoomView } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
import styles from "./preferans-table.module.css";

export function ClaimPanel({view,profiles,busy,command}:{view:RoomView;profiles:SeatProfile[]|null;busy:boolean;command:(action:CommandAction,args?:Record<string,unknown>)=>void}) {
  const c=view.claim;
  if(!c)return null;
  const name=(seat:number)=>profiles?.[seat]?.name||`Игрок ${seat+1}`;
  if(c.status!=="pending")return null;
  const vote=view.my_seat!==null&&c.voters.includes(view.my_seat)&&!c.approved.includes(view.my_seat);
  const labels=claimVoteLabels(view,c.seat);
  return <section className={styles.claimPanel} role="region" aria-label={c.defender_target===undefined?"Все мои":"По своим"}>
    <strong>{c.defender_target===undefined?`${name(c.seat)} говорит, что все взятки его`:`${name(c.seat)} предлагает по своим: ${name(c.voters[0])} — ${c.defender_target} взяток за раздачу`}</strong>
    {c.defender_target===undefined&&<div className={styles.claimCards}>{c.cards.map(card=><span key={`${card.suit}${card.rank}`}><CardArtwork card={card}/></span>)}</div>}
    {vote?<div className={styles.claimVotes}><button type="button" disabled={busy||!!view.controls?.paused} onClick={()=>command("claim_vote",{approve:true})}>{labels.approve}</button><button type="button" disabled={busy||!!view.controls?.paused} onClick={()=>command("claim_vote",{approve:false})}>{labels.reject}</button></div>:<p>Ожидаем: {c.voters.filter(i=>!c.approved.includes(i)).map(name).join(", ")}</p>}
  </section>;
}
