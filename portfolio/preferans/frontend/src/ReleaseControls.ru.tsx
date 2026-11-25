import { useState } from "react";
import { cardId, cardLabel, type CommandAction, type RoomView } from "./game-model.ru";
import type { Decision, PunchChoice } from "./release-model";
import styles from "./preferans-game.module.css";

type Send = (action:CommandAction,args?:Record<string,unknown>)=>void;
const names:Record<Decision,string> = {continue:"Продолжить",redeal:"Пересдать",penalty:"Штраф в гору и продолжить"};
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
  const [selected,setSelected]=useState("");
  const [amount,setAmount]=useState("");
  const incident=view.reveal;
  const proposal=incident?.proposal;
  const seat=view.my_seat;
  const card=view.hand?.find(c=>cardId(c)===selected);
  const disconnected=view.controls?.pause_reasons?.includes("connection_lost");
  const custom=!view.is_passout&&!view.contract;
  const canReport=view.status==="playing"&&seat!==null&&!incident&&!view.controls?.undo&&
    !view.controls?.pause_reasons?.some(reason=>reason!=="connection_lost")&&
    !view.open_hands?.some(h=>h.seat===seat);
  const reportable=(view.hand??[]).filter(c=>!view.revealed_cards?.some(x=>x.seat===seat&&cardId(x.card)===cardId(c)));
  const propose=(decision:Decision)=>{if(incident)command("reveal_propose",{id:incident.id,decision,amount:decision==="penalty"&&custom?Number(amount):null});};
  const validAmount=!custom||(amount!==""&&Number.isSafeInteger(Number(amount))&&Number(amount)>=1&&Number(amount)<=1000);
  return <>
    {view.revealed_cards&&<p role="status">Раскрытые карты: {view.revealed_cards.map(x=>`Игрок ${x.seat+1}: ${cardLabel(x.card)}`).join(" · ")}</p>}
    {incident&&<section className={styles.panel} aria-label="Решение по раскрытой карте">
      <h3>Случайно раскрытая карта</h3><p role="status">Игрок {incident.seat+1}: {cardLabel(incident.card)}. Игра и счётчик приостановлены до согласия всех троих.</p>
      {disconnected&&<p>Ожидаем восстановления связи.</p>}
      {!proposal&&<>{custom&&<label className={styles.field}>Согласуемый штраф до назначения игры<input type="number" min={1} max={1000} value={amount} onChange={e=>setAmount(e.target.value)}/></label>}
        {(["continue","redeal","penalty"] as const).map(decision=><button type="button" key={decision} disabled={busy||Boolean(disconnected)||seat===null||(decision==="penalty"&&!validAmount)} onClick={()=>propose(decision)}>Предложить и согласиться: {names[decision]}</button>)}
      </>}
      {proposal&&<><p>{names[proposal.decision]}{proposal.amount!==null?` (+${proposal.amount} в гору игроку ${incident.seat+1})`:""}. Согласились: {proposal.votes.filter(Boolean).length}/3.</p>
        {seat!==null&&!proposal.votes[seat]&&<div className={styles.actions}>{[true,false].map(approve=><button type="button" key={String(approve)} disabled={busy||Boolean(disconnected)} onClick={()=>command("reveal_vote",{id:incident.id,proposal_id:proposal.id,approve})}>{approve?"Согласен":"Не согласен"}</button>)}</div>}
        <p>Отказ отменяет предложение, но не раскрытие. Можно предложить другое решение.</p></>}
    </section>}
    {canReport&&reportable.length>0&&<details name="preferans-control-group" className={styles.panel}><summary>Случайно показал карту</summary>
      <label className={styles.field}>Раскрытая карта<select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Выбрать карту</option>{reportable.map(c=><option key={cardId(c)} value={cardId(c)}>{cardLabel(c)}</option>)}</select></label>
      <button type="button" disabled={busy||!card||!reportable.some(c=>cardId(c)===selected)} onClick={()=>{if(card&&window.confirm("Эту карту увидят все игроки. Начать согласование?"))command("reveal_report",{card});}}>Сообщить о раскрытии</button>
    </details>}
    {view.punch_choices&&<section className={styles.panel}><h3>Условные удары</h3><p>Шуточные записи. Финансовый результат и места уже зафиксированы.</p>
      {view.punch_choices.map(pair=><div key={`${pair.from}:${pair.to}`}>
        {seat===pair.to&&pair.replacement===null?<Choice pair={pair} busy={busy} command={command}/>:<p>Игрок {pair.from+1} → игрок {pair.to+1}: {pair.bare-(pair.replacement??0)} голых, {pair.ordinary+10*(pair.replacement??0)} обычных{pair.replacement===null?" (ожидает выбора проигравшего)":" (подтверждено)"}.</p>}
      </div>)}
    </section>}
    {view.can_archive&&<details name="preferans-control-group" className={styles.panel}><summary>Архивирование (Owner)</summary><p>Необратимое закрытие незавершённой комнаты без рейтинга, с сохранением истории.</p><button type="button" disabled={busy} onClick={()=>{const reason=window.prompt("Причина архивирования (5–180 символов)");if(reason&&reason.trim().length>=5&&reason.trim().length<=180&&window.confirm("Архивировать незавершённую партию?"))command("archive",{reason:reason.trim()});}}>Архивировать</button></details>}
  </>;
}
