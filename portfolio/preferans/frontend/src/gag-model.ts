import type { RoomView } from "./game-model.ru";
import { actorSeat } from "./table-model";

export const HIDE_DURATION_MS=1400;
export const GAG_MISSING_MS=3200;
export const GAG_FOUND_MS=5200;
export const GAG_RETURN_MS=6600;
export const GAG_FAKE_MS=8000;
export const GAG_TOTAL_MS=11900;
export type GagMark={seat:number;at_ms:number};
export function isGagMark(value:unknown):value is GagMark {
  if(!value||typeof value!=="object")return false;
  const mark=value as GagMark;
  return Object.keys(value).length===2&&[0,1,2].includes(mark.seat)&&Number.isSafeInteger(mark.at_ms)&&mark.at_ms>=0;
}
export function gagPhase(mark:GagMark|undefined,now:number):"fake"|"deal"|null {
  if(!mark)return null;
  const elapsed=Math.max(0,now-mark.at_ms);
  return elapsed<GAG_FAKE_MS?"fake":elapsed<GAG_TOTAL_MS?"deal":null;
}
export function counterTarget(view:RoomView):number|null {
  if(view.my_seat===null||!view.controls||view.controls.counter||view.phase==="misere_offer")return null;
  const target=actorSeat(view);
  return target!==null&&target!==view.my_seat&&view.occupied[target]?target:null;
}
export function counterSeconds(deadline:number|null,remaining:number|undefined,now:number):number {
  return Math.max(0,Math.ceil((deadline===null?remaining??0:deadline-now)/1000));
}
