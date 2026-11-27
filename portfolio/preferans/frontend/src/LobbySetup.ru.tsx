import { useState } from "react";
import type { CommandAction, RoomView } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
import styles from "./preferans-game.module.css";

export function LobbySetup({view,profiles,busy,command,mode="ready"}: {view:RoomView;profiles:SeatProfile[]|null;busy:boolean;mode?:"ready"|"config";command:(action:CommandAction,args:Record<string,unknown>)=>void}) {
  const setup = view.lobby_setup;
  if (!setup) return null;
  return <LobbyConfig key={`${setup.dealer}:${setup.target}:${setup.ruleset}:${setup.ruleset_version}`} view={view} profiles={profiles} busy={busy} command={command} mode={mode}/>;
}
function LobbyConfig({view,profiles,busy,command,mode}: {view:RoomView;profiles:SeatProfile[]|null;busy:boolean;mode:"ready"|"config";command:(action:CommandAction,args:Record<string,unknown>)=>void}) {
  const setup=view.lobby_setup!;
  const [dealer,setDealer]=useState(setup.dealer);
  const [target,setTarget]=useState(String(setup.target));
  const own=view.my_seat;
  const full=view.occupied.every(Boolean);
  const name=(i:number)=>profiles?.[i]?.name||`Игрок ${i+1}`;
  const numeric=Number(target);
  const valid=Number.isInteger(numeric)&&numeric>=2&&numeric<=40&&numeric%2===0;
  return <section className={styles.panel} aria-label={mode==="ready"?"Подготовка партии":"Настройки партии"}>
    <h3>{mode==="ready"?"Готовы играть?":"Настройки партии"}</h3>
    <p>Пуля: {setup.target} · Сдаёт: {name(setup.dealer)} · Правила: {setup.ruleset_name ?? setup.ruleset}, версия {setup.ruleset_version}</p>
    <p>Счётчик: {view.controls?.policy?.counter_seconds ?? 180} с · штраф ×{view.controls?.policy?.counter_multiplier ?? 3} · отмена: {view.controls?.policy?.undo_seconds ?? 120} с</p>
    {mode==="ready"&&<><p>Согласны с правилами и готовы начать?</p>
      <p>{setup.ready.map((ready,i)=>`${name(i)}: ${ready?"готов":"ожидает"}`).join(" · ")}</p></>}
    {view.room_admin && <div className={styles.actions}>
      <label className={styles.field}>Первый сдающий<select value={dealer} onChange={e=>setDealer(Number(e.target.value))}>
        {[0,1,2].map(seat=><option key={seat} value={seat}>{name(seat)}</option>)}
      </select></label>
      <label className={styles.field}>Размер пули<input type="number" min={2} max={40} step={2} value={target} onChange={e=>setTarget(e.target.value)}/></label>
      <button type="button" disabled={busy||Boolean(view.seat_swap)||!valid} onClick={()=>command("lobby_config",{dealer,target:numeric})}>Сохранить параметры и запросить готовность</button>
    </div>}
    {mode==="ready"&&own!==null && <button type="button" disabled={busy||Boolean(view.seat_swap)||!full} className={styles.primary} onClick={()=>command("lobby_ready",{ready:!setup.ready[own]})}>{setup.ready[own]?"Отозвать готовность":"Подтверждаю состав, правила и готовность"}</button>}
  </section>;
}
