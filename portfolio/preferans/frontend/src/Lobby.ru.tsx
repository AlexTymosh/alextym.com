import { useEffect, useState } from "react";
import { safeDirectory, type RoomSummary } from "./table-model";
import { roomAgeMinutes } from "./table-details";
import styles from "./preferans-game.module.css";
import tableStyles from "./preferans-table.module.css";
const names: Record<RoomSummary["status"],string> = {lobby:"Ожидание игроков",playing:"Идёт игра",awaiting_settlement:"Расчёт",between:"Между раздачами",closed:"Завершена",archived:"Архивирована"};
function ageLabel(minutes:number) {
  const days=Math.floor(minutes/1440), hours=Math.floor(minutes%1440/60), mins=minutes%60;
  return `${days?`${days} д. `:""}${hours?`${hours} ч. `:""}${mins} мин.`;
}
export function Lobby({openRoom,create,busy}: {openRoom:(id:string)=>void;create:()=>void;busy:boolean}) {
  const [data,setData] = useState<ReturnType<typeof safeDirectory>>(null);
  const [reload,setReload] = useState(0);
  const [now,setNow]=useState(()=>Date.now());
  const [notice,setNotice]=useState("");
  const [error,setError] = useState("");
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),60_000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{
    const controller = new AbortController();
    fetch("/api/preferans/rooms",{credentials:"same-origin",cache:"no-store",signal:controller.signal})
      .then(async r=>{if(!r.ok) throw new Error(r.status===403?"Для входа нужны права Test или Admin.":"Список комнат недоступен.");const result=safeDirectory(await r.json());if(!result)throw new Error("Некорректный ответ сервера.");if(!controller.signal.aborted){setData(result);setError("");}})
      .catch((e:unknown)=>{if(!controller.signal.aborted){setData(null);setError(e instanceof Error?e.message:"Список комнат недоступен.");}});
    return ()=>controller.abort();
  },[reload]);
  const copy=(id:string)=>{
    const url=new URL("/portfolio/preferans",window.location.origin);url.searchParams.set("room",id);
    if(!navigator.clipboard){setNotice(`Не удалось скопировать: ${url.href}`);return;}
    void navigator.clipboard.writeText(url.href).then(()=>setNotice("Ссылка на игру скопирована.")).catch(()=>setNotice(`Не удалось скопировать: ${url.href}`));
  };
  return <section className={styles.panel} aria-labelledby="preferans-join-heading">
    <h2 id="preferans-join-heading">Создать игру или присоединиться</h2>
    {data?.can_create && <button type="button" className={styles.primary} onClick={create} disabled={busy}>Создать комнату</button>}
    <div className={tableStyles.lobbyHeader}><h3>Доступные комнаты</h3><button type="button" onClick={()=>{setNotice("");setReload(v=>v+1);}}>Обновить</button></div>
    {notice&&<p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p>Загрузка комнат…</p>}
    {data && <div className={tableStyles.roomList}>
      {!data.rooms.length && <p>Нет доступных комнат.</p>}
      {data.rooms.map(room=>{
        const age=roomAgeMinutes(room.created_at_ms,now);
        const created=room.created_at_ms?new Intl.DateTimeFormat("ru-RU",{dateStyle:"short",timeStyle:"short",timeZone:"Europe/London"}).format(room.created_at_ms):null;
        const players=room.occupied.flatMap((occupied,i)=>occupied?[room.player_names?.[i]||`Игрок ${i+1}`]:[]);
        return <div className={tableStyles.roomItem} key={room.room_id}>
          <button type="button" className={tableStyles.roomEnter} disabled={busy} onClick={()=>openRoom(room.room_id)} aria-label={`${room.mine?"Продолжить":"Войти"}: ${created??room.room_id.slice(0,8)}`}>
            <strong>{created?`Комната создана ${created}${room.daily_number?` · №${room.daily_number}`:""}`:"Ранее созданная комната"}</strong>
            {age!==null&&<span>Существует: {ageLabel(age)}</span>}
            <span>{names[room.status]}</span>
            <span>{players.length?`За столом: ${players.join(", ")}`:"Свободная комната"}</span>
            {!!room.waiting_names?.length&&<span>На связи: {room.waiting_names.join(", ")}</span>}
          </button>
          <button type="button" className={tableStyles.roomLink} onClick={()=>copy(room.room_id)} aria-label="Скопировать ссылку на игру">Ссылка на игру</button>
        </div>;
      })}
      {data.truncated && <p>Список ограничен. Другую комнату можно открыть по ссылке.</p>}
    </div>}
  </section>;
}
