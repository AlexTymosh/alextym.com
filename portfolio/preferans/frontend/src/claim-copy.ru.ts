import type { RoomView } from "./game-model.ru";

export function claimVoteLabels(view:RoomView, claimant:number):{approve:string;reject:string} {
  if(view.is_passout)return {approve:"так ему и надо!",reject:"Я против! (вот это я гоню...)"};
  if(view.declarer===claimant&&(view.contract?.kind==="misere"||view.contract?.kind==="misere_no_widow"))return {approve:"Шикарно всунули!",reject:"Я туплю - я против!"};
  return {approve:"Согласен",reject:"Хер там!"};
}
