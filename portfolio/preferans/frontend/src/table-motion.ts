/** All coordinates are taken from the current client's actual layout. */
export const DEAL_DURATION_MS = 3650;
const DEAL_SORT_AT_MS = 3100;
const DEAL_SORT_MS = 450;
export const TRICK_DURATION_MS = 1600;
const DEAL_FLIGHT_MS = 900;
const COLLECT_HOLD_MS = 900;
const COLLECT_FLIGHT_MS = 650;
const center = (r: DOMRect) => ({x:r.left+r.width/2,y:r.top+r.height/2});
export function flightDelta(from:DOMRect,to:DOMRect) {
  const a=center(from),b=center(to);
  return {x:b.x-a.x,y:b.y-a.y};
}
export const localTableScale=(table:HTMLElement):number=>table.offsetWidth?table.getBoundingClientRect().width/table.offsetWidth||1:1;
export function animateDeal(table:HTMLElement, dealer:number, rawOrder:readonly string[]=[],elapsedMs=0,deckOrigin?:DOMRect):()=>void {
  if(elapsedMs>=DEAL_SORT_AT_MS+DEAL_SORT_MS)return ()=>{};
  const source=table.querySelector<HTMLElement>("[data-play-field]");
  if(!source)return ()=>{};
  const origin=deckOrigin??source.getBoundingClientRect();
  const scale=localTableScale(table);
  const unsorted=new Map<HTMLElement,{x:number;y:number}>();
  const layers:{node:HTMLElement;previous:string}[]=[];
  const hands=Array.from({length:3},(_,i)=>{
    const seat=(dealer+1+i)%3;
    const node=table.querySelector<HTMLElement>(`[data-seat="${seat}"]`);
    const own=node?.dataset.position==="bottom";
    const cards=Array.from((own?table:node)?.querySelectorAll<HTMLElement>(own?"[data-own-hand] [data-hand-card] [data-card]":"[data-card-back]")??[]);
    if(!own||cards.length<2)return cards;
    const byId=new Map(cards.map(card=>[card.dataset.card,card]));
    const ordered=rawOrder.map(id=>byId.get(id));
    if(ordered.length!==cards.length||ordered.some(card=>!card)||new Set(ordered).size!==cards.length)return cards;
    const rects=cards.map(card=>card.getBoundingClientRect());
    const left=Math.min(...rects.map(r=>r.left));
    const right=Math.max(...rects.map(r=>r.right));
    const y=rects[0].top;
    const step=(right-left-rects[0].width)/(cards.length-1);
    const original=ordered as HTMLElement[];
    original.forEach((card,index)=>{
      const box=card.getBoundingClientRect();
      unsorted.set(card,{x:left+index*step-box.left,y:y-box.top});
      if(card.parentElement){layers.push({node:card.parentElement,previous:card.parentElement.style.zIndex});card.parentElement.style.zIndex=String(index+1);}
    });
    return original;
  });
  const widow=Array.from(table.querySelectorAll<HTMLElement>("[data-widow-zone] img"));
  const batches:HTMLElement[][]=[];
  for(let round=0;round<5;round++){
    for(const hand of hands)batches.push(hand.slice(round*2,round*2+2));
    if(round===0)batches.push(widow);
  }
  const animations:Animation[]=[];
  batches.forEach((batch,i)=>batch.forEach(card=>{
    if(typeof card.animate!=="function")return;
    const delta=flightDelta(card.getBoundingClientRect(),origin);
    const slot=unsorted.get(card);
    const start={transform:`translate3d(${delta.x/scale}px,${delta.y/scale}px,0) rotate(-8deg) scale(.75)`,opacity:0};
    const delay=i*135;
    if(!slot){
      animations.push(card.animate([start,{transform:"none",opacity:1}],{duration:DEAL_FLIGHT_MS,delay:delay-elapsedMs,easing:"cubic-bezier(.2,.75,.3,1)",fill:"backwards"}));
      return;
    }
    const duration=DEAL_SORT_AT_MS+DEAL_SORT_MS-delay;
    const transform=`translate3d(${slot.x/scale}px,${slot.y/scale}px,0)`;
    animations.push(card.animate([
      {...start,offset:0,easing:"cubic-bezier(.2,.75,.3,1)"},
      {transform,opacity:1,offset:DEAL_FLIGHT_MS/duration},
      {transform,opacity:1,offset:(DEAL_SORT_AT_MS-delay)/duration,easing:"ease-in-out"},
      {transform:"none",opacity:1,offset:1},
    ],{duration,delay:delay-elapsedMs,fill:"both"}));
  }));
  const restoreLayers=()=>layers.forEach(({node,previous})=>{node.style.zIndex=previous;});
  const sortTimer=setTimeout(restoreLayers,Math.max(0,DEAL_SORT_AT_MS-elapsedMs));
  return ()=>{clearTimeout(sortTimer);restoreLayers();animations.forEach(animation=>animation.cancel());};
}
export function animateCollection(table:HTMLElement,winner:number,onFinished?:()=>void):()=>void {
  const target=table.querySelector<HTMLElement>(`[data-trick-train="${winner}"] [data-latest="true"]`);
  if(!target){onFinished?.();return ()=>{};}
  const destination=target.getBoundingClientRect();
  const cards=Array.from(table.querySelectorAll<HTMLElement>("[data-play-field] [data-trick-seat] > span"));
  const animations:Animation[]=[];
  const cleanups:(()=>void)[]=[];
  cards.forEach(card=>{
    if(typeof card.animate!=="function")return;
    // A fixed-position clone uses viewport coordinates and is not affected by rotated trick spots.
    const r=card.getBoundingClientRect(),delta=flightDelta(r,destination);
    const clone=card.cloneNode(true) as HTMLElement;
    clone.setAttribute("aria-hidden","true");clone.setAttribute("inert","");
    Object.assign(clone.style,{position:"fixed",left:`${r.left}px`,top:`${r.top}px`,width:`${r.width}px`,height:`${r.height}px`,margin:"0",pointerEvents:"none",zIndex:"9999"});
    const image=clone.querySelector("img");if(image){image.style.width="100%";image.style.height="100%";}
    (document.fullscreenElement??document.body).append(clone);
    card.style.visibility="hidden";
    const animation=clone.animate([{transform:"none",opacity:1},{transform:`translate3d(${delta.x}px,${delta.y}px,0) scale(.48)`,opacity:1},{transform:`translate3d(${delta.x}px,${delta.y}px,0) scale(.40)`,opacity:0}],{duration:COLLECT_FLIGHT_MS,delay:COLLECT_HOLD_MS,easing:"cubic-bezier(.35,.05,.55,1)",fill:"forwards"});
    animations.push(animation);
    const cleanup=()=>{clone.remove();card.style.visibility="";};
    // Keep the original card hidden until the animation state is cleared.
    animation.onfinish=()=>clone.remove();animation.oncancel=cleanup;
    cleanups.push(cleanup);
  });
  let cancelled=false;
  if(onFinished)void Promise.allSettled(animations.map(animation=>animation.finished)).then(()=>{if(!cancelled)onFinished();});
  return ()=>{
    cancelled=true;
    // Restore synchronously, before a new collection can hide these same elements.
    animations.forEach(animation=>{animation.onfinish=null;animation.oncancel=null;animation.cancel();});
    cleanups.forEach(cleanup=>cleanup());
  };
}
export function animateArrival(table:HTMLElement, seat:number):void {
  const source=table.querySelector<HTMLElement>(`[data-seat="${seat}"] [data-turn]`);
  const target=table.querySelector<HTMLElement>(`[data-trick-seat="${seat}"]`);
  if(!source||!target||!target.firstElementChild||typeof target.animate!=="function")return;
  const d=flightDelta(target.getBoundingClientRect(),source.getBoundingClientRect());
  const scale=localTableScale(table);
  target.animate([{translate:`${d.x/scale}px ${d.y/scale}px`,opacity:.55},{translate:"0px 0px",opacity:1}],{duration:180,easing:"cubic-bezier(.2,.75,.3,1)"});
}

export const GATHER_DURATION_MS=1450;
/** Visual-only collection. The real deck remains on the server. */
export function animateGather(table:HTMLElement):()=>void {
  const target=table.querySelector<HTMLElement>("[data-deck-collect-target]");
  if(!target)return ()=>{};
  const destination=target.getBoundingClientRect(),bounds=table.getBoundingClientRect(),scale=localTableScale(table);
  const nodes=Array.from(table.querySelectorAll<HTMLElement>("[data-trick-train] > button:not([data-awarded]),[data-seat] [data-card-back],[data-seat] [data-card],[data-own-hand] [data-card],[data-widow-zone] img"));
  if(!nodes.length||typeof target.animate!=="function")return ()=>{};
  const deck=target.closest("button");
  const wasInert=deck?.inert??false;
  const animations:Animation[]=[],clones:HTMLElement[]=[];
  table.dataset.gathering="true";
  if(deck)deck.inert=true;
  nodes.forEach((node,i)=>{
    const rect=node.getBoundingClientRect();if(!rect.width||!rect.height)return;
    const clone=node.cloneNode(true) as HTMLElement;
    clone.setAttribute("aria-hidden","true");clone.inert=true;clone.dataset.gatherClone="true";
    clone.removeAttribute("data-latest");clone.removeAttribute("id");
    Object.assign(clone.style,{position:"absolute",left:`${(rect.left-bounds.left)/scale-table.clientLeft}px`,top:`${(rect.top-bounds.top)/scale-table.clientTop}px`,width:`${rect.width/scale}px`,height:`${rect.height/scale}px`,margin:"0",visibility:"visible",pointerEvents:"none",zIndex:"11"});
    table.append(clone);clones.push(clone);
    const d=flightDelta(rect,destination);
    animations.push(clone.animate([{transform:"none",opacity:1},{transform:`translate3d(${d.x/scale}px,${d.y/scale}px,0) rotate(12deg) scale(.45)`,opacity:1},{transform:`translate3d(${d.x/scale}px,${d.y/scale}px,0) scale(.3)`,opacity:0}],{duration:900,delay:i%12*35,fill:"both",easing:"ease-in-out"}));
  });
  let finished=false;
  const finish=()=>{if(finished)return;finished=true;animations.forEach(a=>a.cancel());clones.forEach(n=>n.remove());delete table.dataset.gathering;if(deck)deck.inert=wasInert;};
  const timer=setTimeout(finish,GATHER_DURATION_MS);
  return ()=>{clearTimeout(timer);finish();};
}
