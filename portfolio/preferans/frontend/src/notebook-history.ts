import type { RoomView, NotebookMark } from "./game-model.ru";
type Sheet = NonNullable<RoomView["score_sheet"]>;
/** Read-only cumulative projection; the live score and ledger never change. */
export function notebookAt(sheet:Sheet,cursor:number):Sheet {
  const hill:number[][]=[[],[],[]],pool:number[][]=[[],[],[]],vists:number[][][]=Array.from({length:3},()=>[[],[],[]]);
  const marks:NotebookMark[]=[];
  const steps=(sheet.steps??[]).slice(0,Math.max(0,cursor));
  steps.forEach((step,i)=>step.entries.forEach(e=>{
    const source=e.field==="vist"?sheet.vists[e.seat][e.against!]:sheet[e.field][e.seat];
    const target=e.field==="vist"?vists[e.seat][e.against!]:e.field==="hill"?hill[e.seat]:pool[e.seat];
    target.splice(0,target.length,...source.slice(0,e.index+1));
    if(step.kind==="manual"||i===steps.length-1)marks.push({field:e.field,seat:e.seat,against:e.against,index:e.index,manual:step.kind==="manual"?true:undefined,manual_reason:step.kind==="manual"&&e.reason!=="manual"?e.reason:undefined,latest:i===steps.length-1?true:undefined});
  }));
  return {exact:sheet.exact,hill,pool,vists,marks,steps};
}
