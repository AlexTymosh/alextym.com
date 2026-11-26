export type PunchChoice = {from:number;to:number;bare:number;ordinary:number;replacement:number|null};
const object = (x:unknown): x is Record<string,unknown> => !!x && typeof x === "object" && !Array.isArray(x);
const count = (x:unknown): x is number => typeof x === "number" && Number.isSafeInteger(x) && x >= 0;
const seat = (x:unknown) => x===0||x===1||x===2;
const punch = (x:unknown) => object(x)&&seat(x.from)&&seat(x.to)&&x.from!==x.to&&count(x.bare)&&x.bare>0&&count(x.ordinary)&&(x.replacement===null||(count(x.replacement)&&x.replacement<=x.bare));
export function isReleaseProjection(v:Record<string,unknown>):boolean {
  if(v.can_archive!==undefined&&v.can_archive!==true)return false;
  if(v.status==="archived"&&(!count(v.archived_at_ms)||["hand","legal_cards","open_hands","widow","trick","last_trick","legal_bids","legal_contracts"].some(k=>v[k]!==undefined)))return false;
  if(v.reveal!==undefined||v.revealed_cards!==undefined)return false;
  if(v.punch_choices!==undefined&&(v.status!=="closed"||!seat(v.my_seat)||!Array.isArray(v.punch_choices)||v.punch_choices.length>3||!v.punch_choices.every(punch)))return false;
  return true;
}
