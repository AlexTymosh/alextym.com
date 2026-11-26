import { useState } from "react";
import { type CommandAction, type RoomView } from "./game-model.ru";
import type { PunchChoice } from "./release-model";
import styles from "./preferans-game.module.css";

type Send = (action:CommandAction,args?:Record<string,unknown>)=>void;
function Choice({pair,busy,command}:{pair:PunchChoice;busy:boolean;command:Send}) {
  const [replace,setReplace]=useState("0");
  const n=Number(replace);
  return <div className={styles.field}>
    <span>От игрока {pair.from+1}: {pair.bare} голых + {pair.ordinary} обычных.</span>
    <label>Сколько голых заменить на обычные (1 → 10)<input type="number" min={0} max={pair.bare} step={1} value={replace} onChange={e=>setReplace(e.target.value)}/></label>
    <p>Итог: {pair.bare-n} голых, {pair.ordinary+10*n} обычных.</p>
    <button type="button" disabled={busy||replace===""||!Number.isSafeInteger(n)||n<0||n>pair.bare} onClick={()=>{if(window.confirm("Зафиксировать выбор? Изменить его после подтверждения нельзя."))command("punch_choose",{from:pair.from,replace:n});}}>Подтвердить выбор</button>
  </div>;
}
export function ReleaseControls({view,busy,command}:{view:RoomView;busy:boolean;command:Send}) {
  const seat=view.my_seat;
  return <>
    {view.punch_choices&&<section className={styles.panel}><h3>Условные удары</h3><p>Шуточные записи. Финансовый результат и места уже зафиксированы.</p>
      {view.punch_choices.map(pair=><div key={`${pair.from}:${pair.to}`}>
        {seat===pair.to&&pair.replacement===null?<Choice pair={pair} busy={busy} command={command}/>:<p>Игрок {pair.from+1} → игрок {pair.to+1}: {pair.bare-(pair.replacement??0)} голых, {pair.ordinary+10*(pair.replacement??0)} обычных{pair.replacement===null?" (ожидает выбора проигравшего)":" (подтверждено)"}.</p>}
      </div>)}
    </section>}
    {view.can_archive&&<details name="preferans-control-group" className={styles.panel}><summary>Архивирование (Owner)</summary><p>Необратимое закрытие незавершённой комнаты без рейтинга, с сохранением истории.</p><button type="button" disabled={busy} onClick={()=>{const reason=window.prompt("Причина архивирования (5–180 символов)");if(reason&&reason.trim().length>=5&&reason.trim().length<=180&&window.confirm("Архивировать незавершённую партию?"))command("archive",{reason:reason.trim()});}}>Архивировать</button></details>}
  </>;
}
