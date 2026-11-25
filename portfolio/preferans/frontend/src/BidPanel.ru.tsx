import { useState } from "react";
import { bidLabel, suitSymbol, type Bid, type CommandAction, type RoomView } from "./game-model.ru";
import { BID_GROUPS, bidsInGroup, canHold, mayConcede, type BidGroup } from "./interaction-model";
import styles from "./preferans-table.module.css";

const labels: Record<BidGroup,string> = {"6":"6","7":"7","8":"8","9":"9","10":"10",misere:"Мизер",misere_no_widow:"Мизер без прикупа",ten_no_widow:"10 без прикупа"};
export function BidPanel({view,busy,command}: {view:RoomView;busy:boolean;command:(action:CommandAction,args?:Record<string,unknown>)=>void}) {
  const auction = view.phase === "auction";
  const [conceding,setConceding] = useState(false);
  const canConcede = mayConcede(view);
  const concessionMode = canConcede && conceding;
  const availableBids = auction ? view.legal_bids ?? [] : view.legal_contracts ?? [];
  const bids = concessionMode ? availableBids.filter(b => b.kind === "regular" || b.kind === "ten_no_widow") : availableBids;
  const [group,setGroup] = useState<BidGroup|null>(null);
  const options = group ? bidsInGroup(bids,group) : [];
  const submit = (bid:Bid) => {
    if (concessionMode) {
      if (window.confirm(`Без трёх: ${bidLabel(bid)}?`)) command("without_three",{bid});
    } else command(auction?"bid":"declare",{bid});
  };
  return <div className={styles.bidPanel} aria-label={auction?"Торговля":"Окончательный контракт"}>
    {canConcede&&<button type="button" aria-pressed={concessionMode} disabled={busy} onClick={()=>{setConceding(v=>!v);setGroup(null);}}>Без трёх</button>}
    {concessionMode&&<span className={styles.concessionHint}>Выбери контракт для штрафа</span>}
    <div className={styles.bidGroups}>
      {auction && <button type="button" disabled={busy} onClick={()=>command("pass")}>ПАС</button>}
      {BID_GROUPS.map(key=>{
        const available=bidsInGroup(bids,key);
        if (!available.length && (key==="misere_no_widow"||key==="ten_no_widow")) return null;
        const direct = key==="misere"||key==="misere_no_widow";
        return <button key={key} type="button" disabled={busy||!available.length} aria-expanded={direct?undefined:group===key&&options.length>0}
          onClick={()=>direct&&available.length===1?submit(available[0]):setGroup(old=>old===key?null:key)}>{labels[key]}</button>;
      })}
      {auction&&canHold(view)&&<button type="button" disabled={busy} onClick={()=>command("here")}>Здесь {bidLabel(view.high_bid!)}</button>}
    </div>
    {group&&options.length>0&&<div className={styles.bidSuits} aria-label={`${labels[group]}: доступные масти`}>
      {options.map(bid=><button type="button" key={JSON.stringify(bid)} aria-label={bidLabel(bid)} disabled={busy}
        className={bid.suit==="H"||bid.suit==="D"?styles.redSuit:undefined} onClick={()=>submit(bid)}>{bid.suit?suitSymbol(bid.suit):"БК"}</button>)}
    </div>}
  </div>;
}
