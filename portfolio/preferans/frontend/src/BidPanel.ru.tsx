import { useState } from "react";
import { bidLabel, suitSymbol, type Bid, type CommandAction, type RoomView } from "./game-model.ru";
import { BID_GROUPS, bidsInGroup, canHold, mayConcede, type BidGroup } from "./interaction-model";
import styles from "./preferans-table.module.css";

const labels: Record<BidGroup,string> = {"6":"6","7":"7","8":"8","9":"9","10":"10",misere:"МИЗЕР",misere_no_widow:"МИЗЕР БЕЗ ПРИКУПА",ten_no_widow:"Тотус без прикупа!"};
export function BidPanel({view,busy,command}: {view:RoomView;busy:boolean;command:(action:CommandAction,args?:Record<string,unknown>)=>void}) {
  const auction = view.phase === "auction";
  const canConcede = mayConcede(view);
  const availableBids = auction ? view.legal_bids ?? [] : view.legal_contracts ?? [];
  const bids = availableBids;
  const [group,setGroup] = useState<BidGroup|null>(null);
  const [concedeVersion,setConcedeVersion]=useState<number|null>(null);
  const options = group ? bidsInGroup(bids,group) : [];
  const expanded = group !== null && (options.length > 0 || (group === "10" && bidsInGroup(bids,"ten_no_widow").length > 0));
  const [confirmation,setConfirmation] = useState<{group:BidGroup;version:number}|null>(null);
  const confirmed = confirmation?.version===view.version?confirmation.group:null;
  const submit = (bid:Bid) => {
    command(auction?"bid":"declare",{bid});
    setConfirmation(null);
  };
  if (!auction && (view.winning_bid?.kind === "misere"||view.winning_bid?.kind === "misere_no_widow")) {
    const misere = availableBids.find(b=>b.kind===view.winning_bid?.kind);
    return <div className={styles.bidGroups} aria-label="Окончательный контракт">
      <button type="button" data-bid-tone="sky" disabled={busy||!misere} onClick={()=>misere&&submit(misere)}>{misere?bidLabel(misere):"Мизер"}</button>
      <button type="button" disabled={busy||!misere} onClick={()=>command("misere_offer")}>Показать карты и предложить что я сыграл</button>
    </div>;
  }
  return <div className={styles.bidPanel} aria-label={auction?"Торговля":"Окончательный контракт"}>
    <div className={styles.bidGroups}>
      {canConcede&&(concedeVersion===view.version?<div role="group" aria-label="Подтверждение без трёх">
        <button type="button" data-bid-tone="dark" data-confirm="true" disabled={busy} onClick={()=>{setConcedeVersion(null);command("without_three");}}>Подтвердить «Без трёх»</button>
        <button type="button" disabled={busy} onClick={()=>setConcedeVersion(null)}>Отмена</button>
      </div>:<button type="button" data-bid-tone="dark" disabled={busy} onClick={()=>{setConfirmation(null);setGroup(null);setConcedeVersion(view.version);}}>Без трёх</button>)}
      {auction && <button type="button" disabled={busy} data-bid-tone="dark" onClick={()=>{setConfirmation(null);command("pass");}}>ПАС</button>}
      {BID_GROUPS.filter(key=>key!=="ten_no_widow").map(key=>{
        const available=bidsInGroup(bids,key);
        const totus=key==="10"?bidsInGroup(bids,"ten_no_widow"):[];
        if (!available.length&&!totus.length && (!auction||key==="misere_no_widow"||["misere","misere_no_widow"].includes(view.auction_calls?.[view.my_seat??-1]?.bid?.kind??""))) return null;
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
        return <div key={key}><button type="button" disabled={busy||(!available.length&&!totus.length)} aria-expanded={direct?undefined:group===key} data-bid-muted={expanded&&group!==key?"true":undefined}
          data-bid-tone={direct?"sky":undefined} data-confirm={asking?"true":undefined}
          onClick={choose}>{asking?`${labels[key].replace(/!$/,"").toUpperCase()}, ТЫ УВЕРЕН?`:labels[key]}</button>
          {group===key&&(options.length>0||totus.length>0)&&<span className={styles.bidSuits} aria-label={`${labels[key]}: доступные масти`}>
            {totus.length>0&&<span className={styles.totusOptions}>
              {auction&&confirmed!=="ten_no_widow"?<button type="button" disabled={busy} data-bid-tone="dark" onClick={()=>setConfirmation({group:"ten_no_widow",version:view.version})}>Тотус без прикупа!</button>:<>{totus.map(bid=><button type="button" key={JSON.stringify(bid)} disabled={busy} data-bid-tone="dark" onClick={()=>submit(bid)}>{`Тотус ${bid.suit?suitSymbol(bid.suit):"БК"}${auction?" — подтвердить":""}`}</button>)}</>}
            </span>}
            {options.map(bid=><button type="button" key={JSON.stringify(bid)} aria-label={bidLabel(bid)} disabled={busy}
              data-bid-tone="suit" data-no-trump={bid.suit?undefined:"true"} className={bid.suit==="H"||bid.suit==="D"?styles.redSuit:undefined} onClick={()=>submit(bid)}><span className={styles.suitGlyph} data-no-trump={bid.suit?undefined:"true"}>{bid.suit?suitSymbol(bid.suit):"БК"}</span></button>)}
          </span>}
        </div>;
      })}
      {auction&&canHold(view)&&<button type="button" disabled={busy} onClick={()=>{setConfirmation(null);setGroup(null);command("here");}}>Здесь {bidLabel(view.high_bid!)}</button>}
    </div>

  </div>;
}
