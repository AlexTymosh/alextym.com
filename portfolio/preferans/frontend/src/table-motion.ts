/** All coordinates are taken from the current client's actual layout. */
export const DEAL_DURATION_MS = 3300;
export const TRICK_DURATION_MS = 1600;
const DEAL_FLIGHT_MS = 900;
const COLLECT_HOLD_MS = 900;
const COLLECT_FLIGHT_MS = 650;
const center = (r: DOMRect) => ({x:r.left+r.width/2,y:r.top+r.height/2});
export function flightDelta(from:DOMRect,to:DOMRect) {
  const a=center(from),b=center(to);
  return {x:b.x-a.x,y:b.y-a.y};
}
export function animateDeal(table:HTMLElement, dealer:number):()=>void {
  const source=table.querySelector<HTMLElement>("[data-play-field]");
  if(!source)return ()=>{};
  const origin=source.getBoundingClientRect();
  const hands=Array.from({length:3},(_,i)=>{
    const seat=(dealer+1+i)%3;
    const node=table.querySelector<HTMLElement>(`[data-seat="${seat}"]`);
    const own=node?.dataset.position==="bottom";
    return Array.from((own?table:node)?.querySelectorAll<HTMLElement>(own?"[data-own-hand] [data-hand-card] [data-card]":"[data-card-back]")??[]);
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
    animations.push(card.animate([{transform:`translate3d(${delta.x}px,${delta.y}px,0) rotate(-8deg) scale(.75)`,opacity:0},{transform:"none",opacity:1}],{duration:DEAL_FLIGHT_MS,delay:i*135,easing:"cubic-bezier(.2,.75,.3,1)",fill:"backwards"}));
  }));
  return ()=>animations.forEach(animation=>animation.cancel());
}
export function animateCollection(table:HTMLElement,winner:number):()=>void {
  const target=table.querySelector<HTMLElement>(`[data-trick-train="${winner}"] [data-latest="true"]`);
  if(!target)return ()=>{};
  const destination=target.getBoundingClientRect();
  const cards=Array.from(table.querySelectorAll<HTMLElement>("[data-play-field] [data-trick-seat] > span"));
  const animations:Animation[]=[];
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
  });
  return ()=>animations.forEach(animation=>animation.cancel());
}
export function animateArrival(table:HTMLElement, seat:number):void {
  const source=table.querySelector<HTMLElement>(`[data-seat="${seat}"] [data-turn]`);
  const target=table.querySelector<HTMLElement>(`[data-trick-seat="${seat}"]`);
  if(!source||!target||!target.firstElementChild||typeof target.animate!=="function")return;
  const d=flightDelta(target.getBoundingClientRect(),source.getBoundingClientRect());
  target.animate([{translate:`${d.x}px ${d.y}px`,opacity:.55},{translate:"0px 0px",opacity:1}],{duration:180,easing:"cubic-bezier(.2,.75,.3,1)"});
}
