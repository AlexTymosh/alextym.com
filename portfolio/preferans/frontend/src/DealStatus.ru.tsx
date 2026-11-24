import { useEffect, useState } from "react";
import type { RoomView } from "./game-model.ru";

export function DealStatus({view}: {view:RoomView}) {
  const clock=view.next_deal;
  const [now,setNow]=useState(()=>Date.now());
  useEffect(()=>{
    if (!clock || clock.deadline_ms===null) return;
    const timer=setInterval(()=>setNow(Date.now()),250);
    return ()=>clearInterval(timer);
  },[clock?.deadline_ms,clock?.after_game_id,clock]);
  const paused=clock?.deadline_ms===null||view.controls?.paused;
  const remaining=paused?clock?.remaining_ms??5000:Math.max(0,Math.min(5000,(clock?.deadline_ms??now)-now));
  return <p role="status">{paused?"Новая раздача приостановлена до восстановления игры.":remaining>0?`Следующая раздача через ${Math.ceil(remaining/1000)} с…`:"Ожидаем подтверждение новой раздачи сервером…"}</p>;
}
