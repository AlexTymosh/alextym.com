import { useLayoutEffect, useRef, type RefObject } from "react";

type Rect = Pick<DOMRect,"x"|"y"|"width"|"height">;
export function paperFlight(from:Rect,to:Rect) {
  if(from.width<=0||from.height<=0||to.width<=0||to.height<=0)return null;
  return {x:from.x+from.width/2-to.x-to.width/2,y:from.y+from.height/2-to.y-to.height/2,sx:from.width/to.width,sy:from.height/to.height};
}
/** Use the existing paper elements, not a second interactive or server-side overlay. */
export function usePaperLift(table:RefObject<HTMLElement|null>,open:boolean) {
  const last=useRef<Rect|null>(null);
  const flight=useRef<Animation|null>(null);
  useLayoutEffect(()=>{
    const root=table.current;
    if(!root)return;
    flight.current?.cancel();
    const mini=root.querySelector<HTMLElement>("[data-paper-miniature]");
    const overlay=root.querySelector<HTMLElement>("[data-paper-lift]");
    const reduce=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if(open&&overlay&&mini){
      const target=overlay.getBoundingClientRect();
      last.current=target;
      if(reduce||typeof overlay.animate!=="function")return;
      const shift=paperFlight(mini.getBoundingClientRect(),target);
      if(!shift)return;
      const base=getComputedStyle(overlay).transform;
      flight.current=overlay.animate([{transform:`translate(${shift.x}px,${shift.y}px) ${base==="none"?"":base} rotate(-11deg) scale(${shift.sx},${shift.sy})`},{transform:base}],{duration:420,easing:"cubic-bezier(.2,.75,.3,1)"});
    }else if(!open){
      const from=last.current;last.current=null;
      if(!from||!mini||reduce||typeof mini.animate!=="function"||mini.dataset.sheetDiscarded==="true")return;
      const shift=paperFlight(from,mini.getBoundingClientRect());
      if(!shift)return;
      const base=getComputedStyle(mini).transform;
      flight.current=mini.animate([{transform:`translate(${shift.x}px,${shift.y}px) scale(${shift.sx},${shift.sy})`},{transform:base}],{duration:360,easing:"ease-in-out"});
    }
    return()=>flight.current?.cancel();
  },[table,open]);
}
