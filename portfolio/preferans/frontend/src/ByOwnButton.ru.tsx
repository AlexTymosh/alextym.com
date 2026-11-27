import { useState } from "react";
import type { CommandAction, RoomView } from "./game-model.ru";

export function ByOwnButton({view,busy,command}:{view:RoomView;busy:boolean;command:(action:CommandAction,args?:Record<string,unknown>)=>void}) {
  const [expanded,setExpanded]=useState(false);
  const options=view.by_own_options??[];
  if(!options.length||view.claim?.status==="pending"||view.my_seat!==view.declarer)return null;
  const disabled=busy||!!view.controls?.paused||!!view.controls?.undo;
  const offer=(target:number)=>{setExpanded(false);command("claim_offer",{defender_target:target});};
  return <>
    <button type="button" disabled={disabled} aria-expanded={options.length>1?expanded:undefined}
      onClick={()=>options.length===1?offer(options[0]):setExpanded(v=>!v)}>По своим</button>
    {expanded&&options.length>1&&options.map(target=><button type="button" key={target} disabled={disabled} onClick={()=>offer(target)}>Отдать {target}</button>)}
  </>;
}
