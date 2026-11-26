/** Presentation-only helpers; no accounting or private data. */
import type { RoomView } from "./game-model.ru";
export function notebookAngle(orientation:number):0|90|-90 {
  const position=((orientation%3)+3)%3;
  return position===1?-90:position===2?90:0;
}
export function splitPlayerName(name:string):[string,string] {
  const [first="",...rest]=name.trim().split(/\s+/);
  return [first,rest.join(" ")];
}
export function autoSettlementAllowed(view:RoomView|null):boolean {
  return !!view&&view.status==="awaiting_settlement"&&!view.final_review&&view.room_admin&&view.settlement_options?.regular_choice===false&&
    !view.controls?.paused&&!view.controls?.undo&&!view.settlement_options.passout_pending?.length;
}
