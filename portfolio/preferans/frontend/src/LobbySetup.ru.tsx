import { useState } from "react";
import type { CommandAction, RoomView } from "./game-model.ru";
import styles from "./preferans-game.module.css";

export function LobbySetup({view,busy,command}: {view:RoomView;busy:boolean;command:(action:CommandAction,args:Record<string,unknown>)=>void}) {
  const setup = view.lobby_setup;
  if (!setup) return null;
  return <LobbyConfig key={`${setup.dealer}:${setup.target}:${setup.ruleset}:${setup.ruleset_version}`} view={view} busy={busy} command={command}/>;
}
function LobbyConfig({view,busy,command}: {view:RoomView;busy:boolean;command:(action:CommandAction,args:Record<string,unknown>)=>void}) {
  const setup=view.lobby_setup!;
  const [dealer,setDealer]=useState(setup.dealer);
  const [target,setTarget]=useState(String(setup.target));
  const own=view.my_seat;
  const full=view.occupied.every(Boolean);
  const numeric=Number(target);
  const valid=Number.isInteger(numeric)&&numeric>=1&&numeric<=1000;
  return <section className={styles.panel} aria-label="Подготовка партии">
    <h3>Подготовка партии</h3>
    <p>Пуля: {setup.target} · Сдаёт: Игрок {setup.dealer+1} · Правила: запорожские, версия {setup.ruleset_version}</p>
    <p>Счётчик: {view.controls?.policy?.counter_seconds ?? 180} с · штраф ×{view.controls?.policy?.counter_multiplier ?? 3} · отмена: {view.controls?.policy?.undo_seconds ?? 120} с</p>
    <p>Готовность: {setup.ready.filter(Boolean).length} из 3. {setup.ready.map((ready,i)=>`Игрок ${i+1}: ${ready?"готов":"ожидает"}`).join(" · ")}</p>
    {view.room_admin && <div className={styles.actions}>
      <label className={styles.field}>Первый сдающий<select value={dealer} onChange={e=>setDealer(Number(e.target.value))}>
        {[0,1,2].map(seat=><option key={seat} value={seat}>Игрок {seat+1}</option>)}
      </select></label>
      <label className={styles.field}>Размер пули<input type="number" min={1} max={1000} value={target} onChange={e=>setTarget(e.target.value)}/></label>
      <button type="button" disabled={busy||Boolean(view.seat_swap)||!valid||(dealer===setup.dealer&&numeric===setup.target)} onClick={()=>command("lobby_config",{dealer,target:numeric})}>Сохранить и сбросить готовность</button>
    </div>}
    {own!==null && <button type="button" disabled={busy||Boolean(view.seat_swap)||!full} className={styles.primary} onClick={()=>command("lobby_ready",{ready:!setup.ready[own]})}>{setup.ready[own]?"Отозвать готовность":"Подтверждаю состав, правила и готовность"}</button>}
  </section>;
}
