export function animateDeal(table:HTMLElement, dealer:number):void {
  const source=table.querySelector<HTMLElement>(`[data-seat="${dealer}"] [data-turn]`);
  if(!source)return;
  const origin=source.getBoundingClientRect();
  const cards=Array.from(table.querySelectorAll<HTMLElement>("[data-hand-card] [data-card], [data-card-back], [data-widow-zone] img"));
  cards.forEach((card,i)=>{
    const r=card.getBoundingClientRect();
    const dx=origin.left+origin.width/2-r.left-r.width/2;
    const dy=origin.top+origin.height/2-r.top-r.height/2;
    if(typeof card.animate!=="function")return;
    card.animate([{transform:`translate3d(${dx}px,${dy}px,0) rotate(-8deg) scale(.75)`,opacity:0},{transform:"none",opacity:1}],{duration:300,delay:Math.min(700,Math.floor(i/2)*45),easing:"cubic-bezier(.2,.75,.3,1)",fill:"backwards"});
  });
}
export function animateArrival(table:HTMLElement, seat:number):void {
  const source=table.querySelector<HTMLElement>(`[data-seat="${seat}"] [data-turn]`);
  const target=table.querySelector<HTMLElement>(`[data-trick-seat="${seat}"]`);
  if(!source||!target||!target.firstElementChild||typeof target.animate!=="function")return;
  const a=source.getBoundingClientRect(),b=target.getBoundingClientRect();
  target.animate([{translate:`${a.left+a.width/2-b.left-b.width/2}px ${a.top+a.height/2-b.top-b.height/2}px`,opacity:.55},{translate:"0px 0px",opacity:1}],{duration:180,easing:"cubic-bezier(.2,.75,.3,1)"});
}
