import { cardId, type Card, type RoomView } from "./game-model.ru";

export type HintMessage={game_id:string;version:number;owner:number;card:Card;raised:boolean};
export type HintSender=(message:HintMessage)=>boolean;
export const hintKey=(owner:number,card:Card)=>`${owner}:${cardId(card)}`;
export const hintScope=(view:RoomView)=>`${view.room_id}:${view.game_id}:${view.version}`;

export function canHint(view:RoomView,owner:number,card:Card):boolean {
  const me=view.my_seat,declarer=view.declarer;
  if(view.status!=="playing"||!(["play","opening_lead"] as string[]).includes(view.phase??"")||
    me==null||declarer==null||me===declarer||owner===declarer||![0,1,2].includes(owner)||
    view.is_passout||view.controls?.paused||view.controls?.undo||view.claim?.status==="pending")return false;
  const kind=view.contract?.kind;
  if(kind!=="misere"&&kind!=="misere_no_widow"&&!((kind==="regular"||kind==="ten_no_widow")&&view.defense?.includes("vist")))return false;
  return (owner===me?view.hand:view.open_hands?.find(h=>h.seat===owner)?.cards)?.some(c=>cardId(c)===cardId(card))===true;
}
export function sharedHint(view:RoomView,owner:number,card:Card):boolean {
  // Another defender must already be entitled to see this hand. Never infer hidden cards.
  return view.defense_hints!==undefined&&canHint(view,owner,card)&&
    (owner!==view.my_seat||view.open_hands?.some(h=>h.seat===owner&&h.cards.some(c=>cardId(c)===cardId(card)))===true);
}
