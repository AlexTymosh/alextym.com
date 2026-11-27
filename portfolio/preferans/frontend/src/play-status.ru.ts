import type { RoomView } from "./game-model.ru";
import type { Presence } from "./realtime-client";

export function awardedMessage(view:RoomView,name:(seat:number)=>string):string|null {
  const claim=view.claim;
  if(claim?.status!=="accepted")return null;
  if(claim.awards)return claim.awards.flatMap((n,i)=>n?[`${name(i)}: +${n} взяток`]:[]).join(" · ");
  return `${name(claim.seat)}: +${claim.awarded} взяток`;
}

export function pauseMessage(view:RoomView,presence:Presence[]|null,name:(seat:number)=>string):string {
  const reasons=view.controls?.pause_reasons??[];
  const labels:string[]=[];
  if(reasons.includes("connection_lost")){
    const missing=presence?.flatMap((state,seat)=>state!=="online"?[name(seat)]:[])??[];
    labels.push(missing.length?`ожидаем связь: ${missing.join(", ")}`:"ожидаем восстановления связи");
  }
  if(reasons.includes("shared_overlay")){
    const overlay=view.presentation?.overlay;
    const names:Record<string,string>={score_sheet:"листик",last_trick:"последнюю взятку",widow_replay:"прикуп",discard_replay:"снос",radio:"магнитофон"};
    labels.push(overlay?`${name(overlay.seat)} смотрит ${names[overlay.kind]??"общую панель"}`:"открыта общая панель");
  }
  if(view.presentation?.break)labels.push("общий перерыв");
  if(view.controls?.undo)labels.push("голосование за отмену");
  return labels.length?`Пауза · ${labels.join(" · ")}`:"Пауза · ожидание общего решения";
}

/** Bidding copy follows the authoritative passout level and actual calls. */
export function auctionMessage(view:RoomView):string|null {
  if(view.phase!=="auction")return null;
  if(view.high_bid?.kind==="misere"){
    if(view.my_seat!==null&&view.auction_calls?.[view.my_seat]?.bid?.kind==="misere")return null;
    return "Ну, ты играешь 9-ную?";
  }
  if(view.previous_passout===8&&!view.high_bid&&(view.auction_calls??[]).filter(call=>call?.kind==="pass").length===2)return "Чё, еще раз распасы?!";
  const level=view.score?.passout_level;
  return level===7?"Распасы, 7-ая":level===8?"Распасы, 8-ная":null;
}

// Derive the forced suit from the authoritative legal move list, not from the
// apparent leading card (passouts and obligatory trump can differ).
export function illegalCardMessage(view:RoomView):string {
  const suits=new Set((view.legal_cards??[]).map(card=>card.suit));
  const suit=suits.size===1?Array.from(suits)[0]:null;
  const labels={S:"пики",C:"трефы",D:"бубны",H:"червы"};
  return suit?`Ты чё, слепой? У тебя ${labels[suit]} есть!`:"Этой картой сейчас ходить нельзя.";
}
export function declarationMessage(view:RoomView,name:(seat:number)=>string):string {
  const seat=view.declarer??view.turn;
  return seat==null?"Ожидаем объявления игры":`${name(seat)} думает какую игру объявить`;
}
