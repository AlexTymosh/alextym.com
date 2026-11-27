import type { Card, RoomView } from "./game-model.ru";

export type Claim = {
  seat:number; status:"pending"|"accepted"|"rejected"; voters:number[];
  approved:number[]; rejected_by:number|null; awarded:number; cards:Card[];
  defender_target?:number; awards?:number[];
};
const seat=(x:unknown):x is number=>typeof x==="number"&&[0,1,2].includes(x);
const seats=(x:unknown):x is number[]=>Array.isArray(x)&&x.length<=2&&x.every(seat)&&new Set(x).size===x.length;
export function validClaim(value:unknown, view:Record<string,unknown>):boolean {
  if(!value||typeof value!=="object"||!seat(view.my_seat))return false;
  const c=value as Claim;
  const own=c.defender_target!==undefined;
  if(own&&(![1,2,3,4].includes(c.defender_target!)||c.seat!==view.declarer||!Array.isArray(c.awards)||c.awards.length!==3||!c.awards.every(n=>Number.isInteger(n)&&n>=0&&n<=10)||c.awards.reduce((a,b)=>a+b,0)!==c.awarded||!Array.isArray(c.voters)||c.voters.length!==1||!Array.isArray(c.cards)||c.cards.length!==0))return false;
  if(!own&&c.awards!==undefined)return false;
  return seat(c.seat)&&["pending","accepted","rejected"].includes(c.status)&&seats(c.voters)&&c.voters.length>0&&!c.voters.includes(c.seat)&&
    seats(c.approved)&&c.approved.every(i=>c.voters.includes(i))&&
    (c.status==="rejected"?seat(c.rejected_by)&&c.voters.includes(c.rejected_by)&&!c.approved.includes(c.rejected_by):c.rejected_by===null)&&
    Number.isInteger(c.awarded)&&c.awarded>=0&&c.awarded<=10&&
    (c.status==="accepted"?c.awarded>0&&c.approved.length===c.voters.length&&view.phase==="finished":c.awarded===0&&view.status==="playing"&&c.approved.length<c.voters.length)&&
    Array.isArray(c.cards)&&c.cards.length<=10&&(c.status==="pending"||c.cards.length===0)&&
    c.cards.every(card=>card&&["S","C","D","H"].includes(card.suit)&&Number.isInteger(card.rank)&&card.rank>=7&&card.rank<=14);
}
export const claimPending=(view:RoomView)=>view.claim?.status==="pending";
export function actualTrickCount(view:RoomView,seat:number):number {
  return Math.max(0,(view.tricks_won?.[seat]??0)-(view.claim?.status==="accepted"?(view.claim.awards?.[seat]??(view.claim.seat===seat?view.claim.awarded:0)):0));
}
