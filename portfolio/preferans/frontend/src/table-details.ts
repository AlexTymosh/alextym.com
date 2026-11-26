/** Display-only preferences and clocks. No storage/network/game commands. */
export const ACTIVITY_SECONDS = 180;
export function activityProgress(since:number|undefined, now:number):number {
  if(since===undefined||!Number.isFinite(since)||!Number.isFinite(now))return 0;
  return Math.max(0,Math.min(100,(now-since)/(ACTIVITY_SECONDS*10)));
}
export function parseTransparency(value:string|null):number|null {
  if(value===null||value.trim()==="")return null;
  const amount=Number(value);
  return Number.isInteger(amount)&&amount>=0&&amount<=75&&amount%5===0?amount:null;
}
export function effectiveOpacity(theme:string,transparency:number|null):number {
  const valid=transparency===null?null:parseTransparency(String(transparency));
  return valid===null?(theme==="glass"?.5:1):1-valid/100;
}
export function roomAgeMinutes(created:number|null|undefined,now:number):number|null {
  if(typeof created!=="number"||!Number.isFinite(created)||created<=0||!Number.isFinite(now))return null;
  return Math.max(0,Math.floor((now-created)/60_000));
}
