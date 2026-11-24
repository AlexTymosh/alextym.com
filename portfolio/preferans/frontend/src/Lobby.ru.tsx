import { useEffect, useState, type ChangeEvent } from "react";
import { safeDirectory, type RoomSummary } from "./table-model";
import styles from "./preferans-game.module.css";
import tableStyles from "./preferans-table.module.css";
const names: Record<RoomSummary["status"],string> = {lobby:"Ожидание игроков",playing:"Идёт игра",awaiting_settlement:"Расчёт",between:"Между раздачами",closed:"Завершена"};
export function Lobby({roomInput,setRoomInput,openRoom,create,busy}: {roomInput:string;setRoomInput:(s:string)=>void;openRoom:(id:string)=>void;create:()=>void;busy:boolean}) {
  const [data,setData] = useState<ReturnType<typeof safeDirectory>>(null);
  const [reload,setReload] = useState(0);
  const [error,setError] = useState("");
  useEffect(()=>{
    const controller = new AbortController();
    fetch("/api/preferans/rooms",{credentials:"same-origin",cache:"no-store",signal:controller.signal})
      .then(async r=>{if(!r.ok) throw new Error(r.status===403?"Для входа нужны права Test или Admin.":"Список комнат недоступен.");const result=safeDirectory(await r.json());if(!result)throw new Error("Некорректный ответ сервера.");if(!controller.signal.aborted){setData(result);setError("");}})
      .catch((e:unknown)=>{if(!controller.signal.aborted){setData(null);setError(e instanceof Error?e.message:"Список комнат недоступен.");}});
    return ()=>controller.abort();
  },[reload]);
  return <section className={styles.panel} aria-labelledby="preferans-join-heading">
    <h2 id="preferans-join-heading">Создать игру или присоединиться</h2>
    <p>Три отдельных аккаунта с доступом Test или Admin. Комнату создаёт администратор проекта.</p>
    {data?.can_create && <button type="button" className={styles.primary} onClick={create} disabled={busy}>Создать комнату</button>}
    <div className={tableStyles.lobbyHeader}><h3>Доступные комнаты</h3><button type="button" onClick={()=>setReload(v=>v+1)}>Обновить</button></div>
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p>Загрузка комнат…</p>}
    {data && <div className={tableStyles.roomList}>
      {!data.rooms.length && <p>Нет доступных комнат.</p>}
      {data.rooms.map(room=><div className={tableStyles.roomItem} key={room.room_id}><div><strong>Комната {room.room_id.slice(0,8)}</strong><p>{names[room.status]} · {room.occupied.filter(Boolean).length}/3</p></div><button type="button" disabled={busy} onClick={()=>openRoom(room.room_id)}>{room.mine?"Продолжить":"Войти"}</button></div>)}
      {data.truncated && <p>Список ограничен. Другую комнату можно открыть по коду.</p>}
    </div>}
    <div className={styles.joinField}><label htmlFor="room-id">Код приглашения</label><input id="room-id" spellCheck={false} autoComplete="off" value={roomInput} onChange={(e:ChangeEvent<HTMLInputElement>)=>setRoomInput(e.target.value.trim().toLowerCase())} placeholder="32 символа"/>
      <button type="button" onClick={()=>openRoom(roomInput)} disabled={busy || !/^[a-f0-9]{32}$/.test(roomInput)}>Найти комнату</button></div>
  </section>;
}
