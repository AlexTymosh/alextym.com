import type { Card } from "./game-model.ru";

export type Decision = "continue" | "redeal" | "penalty";
export type RevealedCard = {seat:number;card:Card};
export type Reveal = RevealedCard & {id:number;game_id:string;proposal:null|{id:number;decision:Decision;amount:number|null;votes:boolean[]}};
export type PunchChoice = {from:number;to:number;bare:number;ordinary:number;replacement:number|null};
const object = (x:unknown): x is Record<string,unknown> => !!x && typeof x === "object" && !Array.isArray(x);
const count = (x:unknown): x is number => typeof x === "number" && Number.isSafeInteger(x) && x >= 0;
const seat = (x:unknown) => x===0||x===1||x===2;
const card = (x:unknown) => object(x) && ["S","C","D","H"].includes(String(x.suit)) && typeof x.rank==="number" && Number.isInteger(x.rank) && x.rank>=7 && x.rank<=14;
const exposed = (x:unknown) => object(x)&&seat(x.seat)&&card(x.card);
const punch = (x:unknown) => object(x)&&seat(x.from)&&seat(x.to)&&x.from!==x.to&&count(x.bare)&&x.bare>0&&count(x.ordinary)&&(x.replacement===null||(count(x.replacement)&&x.replacement<=x.bare));
export function isReleaseProjection(v:Record<string,unknown>):boolean {
  if(v.can_archive!==undefined&&v.can_archive!==true)return false;
  if(v.status==="archived"&&(!count(v.archived_at_ms)||["hand","legal_cards","open_hands","widow","trick","last_trick","legal_bids","legal_contracts"].some(k=>v[k]!==undefined)))return false;
  if(v.revealed_cards!==undefined&&(v.status!=="playing"||!seat(v.my_seat)||!Array.isArray(v.revealed_cards)||v.revealed_cards.length>32||!v.revealed_cards.every(exposed)))return false;
  if(v.reveal!==undefined){
    const r=v.reveal;
    if(v.status!=="playing"||!seat(v.my_seat)||!object(r)||!exposed(r)||!count(r.id)||r.game_id!==v.game_id)return false;
    const p=r.proposal;
    if(p!==null&&(!object(p)||!count(p.id)||!["continue","redeal","penalty"].includes(String(p.decision))||!Array.isArray(p.votes)||p.votes.length!==3||!p.votes.every(x=>typeof x==="boolean")|| (p.decision==="penalty"?(!count(p.amount)||p.amount===0):p.amount!==null)))return false;
  }
  if(v.punch_choices!==undefined&&(v.status!=="closed"||!seat(v.my_seat)||!Array.isArray(v.punch_choices)||v.punch_choices.length>3||!v.punch_choices.every(punch)))return false;
  return true;
}
