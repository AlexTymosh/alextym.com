import {useEffect,useState} from "react";
import type {RoomView} from "./game-model.ru";
import {counterSeconds} from "./gag-model";
import styles from "./preferans-table.module.css";

export function CounterDisplay({view,name,serverNow}:{view:RoomView;name:(seat:number)=>string;serverNow:()=>number}) {
  const [now,setNow]=useState(()=>serverNow());
  const counter=view.controls?.counter;
  const running=counter?.deadline_ms!=null;
  useEffect(()=>{
    if(!running)return;
    const id=setInterval(()=>setNow(serverNow()),200);
    return()=>clearInterval(id);
  },[running,serverNow]);
  if(!counter)return null;
  const left=counterSeconds(counter.deadline_ms,counter.remaining_ms,now);
  const multiplier=view.controls?.policy?.counter_multiplier??3;
  return <div className={styles.counterDisplay}>
    <strong>{name(counter.initiator)} поставил на счётчик {name(counter.target)}</strong>
    <span className={styles.counterDigits} aria-live="off" aria-label={`Осталось ${left} секунд`}>{String(Math.floor(left/60)).padStart(2,"0")}:{String(left%60).padStart(2,"0")}</span>
    <small>Не успеешь - штраф {multiplier}х в гору!</small>
    <small>{counter.penalty} в гору за интервал · истечений: {counter.periods}{counter.deadline_ms===null?" · пауза":""}</small>
  </div>;
}
