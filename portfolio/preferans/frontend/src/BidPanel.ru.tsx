import { useState } from "react";
import { bidLabel, suitSymbol, type Bid, type CommandAction, type RoomView } from "./game-model.ru";
import { BID_GROUPS, bidsInGroup, canHold, mayConcede, type BidGroup } from "./interaction-model";
import styles from "./preferans-table.module.css";

const labels: Record<BidGroup,string> = {"6":"6","7":"7","8":"8","9":"9","10":"10",misere:"МИЗЕР",misere_no_widow:"МИЗЕР БЕЗ ПРИКУПА",ten_no_widow:"Тотус без прикупа!"};
export function BidPanel({view,busy,command}: {view:RoomView;busy:boolean;command:(action:CommandAction,args?:Record<string,unknown>)=>void}) {
  const auction = view.phase === "auction";
  const [conceding,setConceding] = useState(false);
  const canConcede = mayConcede(view);
  const concessionMode = canConcede && conceding;
  const availableBids = auction ? view.legal_bids ?? [] : view.legal_contracts ?? [];
  const bids = concessionMode ? availableBids.filter(b => b.kind === "regular" || b.kind === "ten_no_widow") : availableBids;
  const [group,setGroup] = useState<BidGroup|null>(null);
  const options = group ? bidsInGroup(bids,group) : [];
  const [confirmation,setConfirmation] = useState<{group:BidGroup;version:number}|null>(null);
  const confirmed = confirmation?.version===view.version?confirmation.group:null;
  const submit = (bid:Bid) => {
    if (concessionMode) {
      if (window.confirm(`Без трёх: ${bidLabel(bid)}?`)) command("without_three",{bid});
    } else command(auction?"bid":"declare",{bid});
    setConfirmation(null);
  };
  if (!auction && view.winning_bid?.kind === "misere") {
    const misere = availableBids.find(b=>b.kind==="misere");
    return <div className={styles.bidGroups} aria-label="Окончательный контракт">
      <button type="button" data-bid-tone="sky" disabled={busy||!misere} onClick={()=>misere&&submit(misere)}>Мизер</button>
      <button type="button" disabled={busy||!misere} onClick={()=>command("misere_offer")}>Предложить, что я сыграл</button>
    </div>;
  }
  return <div className={styles.bidPanel} aria-label={auction?"Торговля":"Окончательный контракт"}>
    {canConcede&&<button type="button" aria-pressed={concessionMode} disabled={busy} onClick={()=>{setConceding(v=>!v);setGroup(null);}}>Без трёх</button>}
    {concessionMode&&<span className={styles.concessionHint}>Выбери контракт для штрафа</span>}
    <div className={styles.bidGroups}>
      {auction && <button type="button" disabled={busy} data-bid-tone="dark" onClick={()=>{setConfirmation(null);command("pass");}}>ПАС</button>}
      {BID_GROUPS.filter(key=>key!=="ten_no_widow").map(key=>{
        const available=bidsInGroup(bids,key);
        const totus=key==="10"?bidsInGroup(bids,"ten_no_widow"):[];
        if (!available.length&&!totus.length && (!auction||key==="misere_no_widow")) return null;
        const direct = key==="misere"||key==="misere_no_widow";
        const special = direct;
        const needsConfirm = auction&&special;
        const asking = needsConfirm&&confirmed===key;
        const choose = () => {
          if(needsConfirm&&!asking){setConfirmation({group:key,version:view.version});setGroup(null);return;}
          setConfirmation(null);
          if(special&&available.length===1)submit(available[0]);
          else setGroup(old=>old===key?null:key);
        };
        return <div key={key}><button type="button" disabled={busy||(!available.length&&!totus.length)} aria-expanded={direct?undefined:group===key}
          data-bid-tone={direct?"sky":undefined} data-confirm={asking?"true":undefined}
          onClick={choose}>{asking?`${labels[key].replace(/!$/,"").toUpperCase()}, ТЫ УВЕРЕН?`:labels[key]}</button>
          {group===key&&(options.length>0||totus.length>0)&&<span className={styles.bidSuits} aria-label={`${labels[key]}: доступные масти`}>
            {totus.length>0&&<span className={styles.totusOptions}>
              {auction&&confirmed!=="ten_no_widow"?<button type="button" disabled={busy} data-bid-tone="dark" onClick={()=>setConfirmation({group:"ten_no_widow",version:view.version})}>Тотус без прикупа!</button>:<>{totus.map(bid=><button type="button" key={JSON.stringify(bid)} disabled={busy} data-bid-tone="dark" onClick={()=>submit(bid)}>{`Тотус ${bid.suit?suitSymbol(bid.suit):"БК"}${auction?" — подтвердить":""}`}</button>)}</>}
            </span>}
            {options.map(bid=><button type="button" key={JSON.stringify(bid)} aria-label={bidLabel(bid)} disabled={busy}
              className={bid.suit==="H"||bid.suit==="D"?styles.redSuit:undefined} onClick={()=>submit(bid)}>{bid.suit?suitSymbol(bid.suit):"БК"}</button>)}
          </span>}
        </div>;
      })}
      {auction&&canHold(view)&&<button type="button" disabled={busy} onClick={()=>{setConfirmation(null);setGroup(null);command("here");}}>Здесь {bidLabel(view.high_bid!)}</button>}
    </div>

  </div>;
}
