/** Pointer-driven ghost. Existing drag/drop handlers remain authoritative. */
export function attachCardPointerDrag(root: Document): () => void {
  let active: {source:HTMLButtonElement; pointer:number; x:number; y:number; rect:DOMRect; ghost:HTMLElement|null; transfer:DataTransfer|null}|null=null;
  let suppressClickUntil=0;
  const end=(event?:PointerEvent,drop=false)=>{
    const a=active;if(!a)return;active=null;
    if(a.ghost){
      a.ghost.remove();delete a.source.dataset.pointerDragging;
      if(drop&&event&&a.transfer){const target=root.elementFromPoint(event.clientX,event.clientY);target?.dispatchEvent(new DragEvent("drop",{bubbles:true,cancelable:true,dataTransfer:a.transfer}));}
      a.source.dispatchEvent(new DragEvent("dragend",{bubbles:true,dataTransfer:a.transfer}));
      suppressClickUntil=performance.now()+250;
    }
    if(a.source.hasPointerCapture(a.pointer))a.source.releasePointerCapture(a.pointer);
  };
  const down=(event:PointerEvent)=>{
    if(active||event.button!==0||!event.isPrimary||!(event.target instanceof Element))return;
    const source=event.target.closest<HTMLButtonElement>("[data-table-view] button[data-card][draggable=true], [data-table-view] button[data-pointer-drag][draggable=true]");
    if(!source||source.disabled)return;
    active={source,pointer:event.pointerId,x:event.clientX,y:event.clientY,rect:source.getBoundingClientRect(),ghost:null,transfer:null};
  };
  const move=(event:PointerEvent)=>{
    const a=active;if(!a||a.pointer!==event.pointerId)return;
    if(!a.source.isConnected){end();return;}
    const dx=event.clientX-a.x,dy=event.clientY-a.y;
    if(!a.ghost&&Math.hypot(dx,dy)<4)return;
    event.preventDefault();
    if(!a.ghost){
      const transfer=new DataTransfer();
      if(!a.source.dispatchEvent(new DragEvent("dragstart",{bubbles:true,cancelable:true,dataTransfer:transfer}))){end();return;}
      a.transfer=transfer;
      const ghost=a.source.cloneNode(true) as HTMLElement;
      ghost.removeAttribute("id");ghost.setAttribute("aria-hidden","true");ghost.setAttribute("inert","");
      Object.assign(ghost.style,{position:"fixed",left:`${a.rect.left}px`,top:`${a.rect.top}px`,width:`${a.rect.width}px`,height:`${a.rect.height}px`,padding:"0",border:"0",background:"transparent",pointerEvents:"none",zIndex:"10000",margin:"0",transition:"none",boxShadow:"0 8px 24px #0008",borderRadius:"5px"});
      const image=ghost.querySelector("img");if(image){image.style.width="100%";image.style.height="100%";}
      (root.fullscreenElement??root.body).append(ghost);a.ghost=ghost;a.source.dataset.pointerDragging="true";
      a.source.setPointerCapture(a.pointer);
    }
    a.ghost.style.transform=`translate3d(${dx}px,${dy}px,0)`;
  };
  const up=(event:PointerEvent)=>{if(active?.pointer===event.pointerId)end(event,true);};
  const cancel=(event:PointerEvent)=>{if(active?.pointer===event.pointerId)end();};
  const native=(event:DragEvent)=>{if(event.isTrusted&&active)event.preventDefault();};
  const click=(event:MouseEvent)=>{if(performance.now()<suppressClickUntil&&event.target instanceof Element&&event.target.closest("[data-table-view] button[data-card], [data-table-view] button[data-pointer-drag]")){event.preventDefault();event.stopPropagation();}};
  const blur=()=>end();window.addEventListener("blur",blur);
  root.addEventListener("pointerdown",down,true);root.addEventListener("pointermove",move,{capture:true,passive:false});root.addEventListener("pointerup",up,true);root.addEventListener("pointercancel",cancel,true);root.addEventListener("dragstart",native,true);root.addEventListener("click",click,true);
  return ()=>{end();window.removeEventListener("blur",blur);root.removeEventListener("pointerdown",down,true);root.removeEventListener("pointermove",move,true);root.removeEventListener("pointerup",up,true);root.removeEventListener("pointercancel",cancel,true);root.removeEventListener("dragstart",native,true);root.removeEventListener("click",click,true);};
}
