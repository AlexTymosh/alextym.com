import { useEffect, useRef, useState, type ReactNode } from "react";
import { CardArtwork } from "./CardArtwork.ru";
import { bidLabel, cardId, cardLabel, type Card, type RoomView } from "./game-model.ru";
import type { Presence } from "./realtime-client";
import { actorSeat, opponentCards, seatPosition, tableSeats, type Seat, type SeatProfile } from "./table-model";
import styles from "./preferans-table.module.css";
import { animationBetween, replayWidow, visibleWidow } from "./interaction-model";

const positionNames = { left: "Слева", right: "Справа", bottom: "Перед собой" };
const statuses = { online: "В игре", reconnecting: "Переподключение", offline: "Отключён", unknown: "Связь неизвестна" };
const fallbackName = (seat: number) => `Игрок ${seat + 1}`;

function Avatar({ seat, profile, active, presence, occupied, own }: {
  seat: Seat; profile?: SeatProfile; active: boolean; presence?: Presence; occupied: boolean; own: boolean;
}) {
  const name = occupied ? profile?.name || fallbackName(seat) : "Свободное место";
  const link = occupied ? presence || "unknown" : "unknown";
  return <div className={styles.identity}>
    <div className={`${styles.avatar} ${active ? styles.activeAvatar : ""}`} data-turn={active ? "true" : "false"}>
      {profile?.avatar && occupied ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={profile.avatar} alt="" width={64} height={64} draggable={false} />
      ) : <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="31" fill="#263e39"/><circle cx="32" cy="24" r="11" fill="#d5c5a2"/><path d="M12 55c1-14 10-21 20-21s19 7 20 21" fill="#d5c5a2"/></svg>}
      {occupied && <span className={styles.connectionDot} data-presence={link} title={statuses[link]} />}
    </div>
    <div className={styles.identityText}><strong title={name}>{name}{own ? " (ты)" : ""}</strong>
      {occupied && <span className={styles.connectionText}>{statuses[link]}{active ? " · Ходит" : ""}</span>}
    </div>
  </div>;
}

function SeatAtTable({ view, seat, profiles, presence, renderOpenCard }: {
  view: RoomView; seat: Seat; profiles: SeatProfile[] | null; presence: Presence[] | null;
  renderOpenCard: (card: Card, seat: Seat) => ReactNode;
}) {
  const own = view.my_seat === seat;
  const position = seatPosition(view.my_seat, seat)!;
  const cards = opponentCards(view, seat);
  const active = actorSeat(view) === seat;
  return <section className={`${styles.seat} ${styles[position]}`} data-seat={seat} data-position={position}
    aria-label={`${positionNames[position]}: ${profiles?.[seat]?.name || fallbackName(seat)}${own ? ", ты" : ""}`}>
    <Avatar seat={seat} profile={profiles?.[seat]} active={active} presence={presence?.[seat]} occupied={view.occupied[seat]} own={own} />
    <div className={styles.seatMeta}>
      {view.phase === "auction" && view.auction_calls?.[seat] && <span className={styles.callBubble}>
        {view.auction_calls[seat]?.kind === "pass" ? "ПАС" : `${view.auction_calls[seat]?.kind === "here" ? "Здесь " : ""}${view.auction_calls[seat]?.bid ? bidLabel(view.auction_calls[seat]!.bid!) : ""}`}
      </span>}
      {view.defense?.[seat] && ["defense_first","defense_second","defense_reconsider","choose_mode","opening_lead","play"].includes(view.phase ?? "") && <span className={styles.callBubble}>{view.defense[seat]==="vist"?"Вист":view.defense[seat]==="half"?"Полвиста":"Пас"}</span>}
      {view.dealer === seat && <span>Сдаёт</span>}
      {view.declarer === seat && <span>Заказчик</span>}
      {view.turn === seat && view.controller !== undefined && view.controller !== null && view.controller !== seat && <span>Открытая рука в ходе</span>}
      {view.tricks_won && <span>Взяток: {view.tricks_won[seat] ?? 0}</span>}
    </div>
    {!own && cards.count > 0 && <div className={`${styles.opponentHand} ${cards.open ? styles.openHand : ""}`}
      aria-label={cards.open ? `Открытая рука: ${fallbackName(seat)}` : `Закрытых карт: ${cards.count}`}>
      {cards.open ? cards.open.map(card => <div className={styles.rivalCard} key={cardId(card)}>{renderOpenCard(card,seat)}</div>)
        : Array.from({length:cards.count},(_,i)=><span className={styles.rivalCard} key={i} data-card-back="true"><CardArtwork decorative /></span>)}
    </div>}
  </section>;
}

function CenterCards({ view, collecting, onWidow, onField }: { view: RoomView; collecting: boolean; onWidow?: () => void; onField?: () => void }) {
  const widow = visibleWidow(view);
  const publicWidow = replayWidow(view);
  const [replay,setReplay] = useState(false);
  const showReplay = replay && publicWidow.length > 0;
  const shown = collecting ? view.last_trick ?? [] : view.trick ?? [];
  const names = tableSeats(view.my_seat);
  return <div className={styles.center}>
    <div className={styles.widow} aria-label="Прикуп">
      {(widow.count > 0 || showReplay) && <><span className={styles.zoneLabel}>Прикуп</span><div className={styles.widowCards}>
        {Array.from({length:showReplay?publicWidow.length:widow.count},(_,i)=><span key={i} className={styles.tableCard}><CardArtwork card={(showReplay?publicWidow:widow.cards)[i]}/></span>)}
      </div></>}
      {widow.count === 0 && publicWidow.length > 0 && <button type="button" aria-expanded={showReplay} onClick={()=>onWidow ? onWidow() : setReplay(v=>!v)}>{showReplay?"Скрыть прикуп":"Показать прикуп"}</button>}
    </div>
    <div className={styles.trickField} aria-label="Текущая взятка" data-collecting={collecting ? seatPosition(view.my_seat, view.last_trick_winner ?? -1) ?? undefined : undefined}>
      {(["left","right","bottom"] as const).map(position => {
        const played = shown.find(p=>p.owner===names[position]);
        return <div key={position} className={`${styles.trickSpot} ${styles[`trick_${position}`]}`} data-trick-seat={names[position]}>
          {played && <span className={styles.tableCard}><CardArtwork card={played.card}/></span>}
        </div>;
      })}
      {!shown.length && <span className={styles.fieldHint}>{view.status === "lobby" ? "Сбор игроков" : "Поле розыгрыша"}</span>}
      {onField && <button type="button" className={styles.closeSharedField} onClick={onField}>Закрыть общий просмотр</button>}
    </div>
    {view.high_bid && view.phase === "auction" && <p className={styles.contract}>Торговля · {bidLabel(view.high_bid)}</p>}
    {view.contract && <p className={styles.contract}>Контракт · {bidLabel(view.contract)}</p>}
    {view.contract?.kind === "regular" && view.contract.level === 6 && view.contract.suit === "S" && <p className={styles.contract}>Обязаловка</p>}
    {view.is_passout && <p className={styles.contract}>Распасы</p>}
  </div>;
}

export function GameTable({view, profiles, presence, hand, actions, renderOpenCard, objects, onWidow, onField, sharedPanel}: {
  view: RoomView; profiles: SeatProfile[] | null; presence: Presence[] | null;
  hand: ReactNode; actions: ReactNode; renderOpenCard: (card: Card, seat: Seat) => ReactNode;
  objects?: ReactNode; sharedPanel?: ReactNode; onWidow?: () => void; onField?: () => void;
}) {
  const seats = tableSeats(view.my_seat);
  const inLobby = view.status === "lobby";
  const previous = useRef<RoomView|null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const [animation,setAnimation] = useState<{kind:"deal"|"trick";game:string|null;count:number}|null>(null);
  useEffect(()=>{
    const before=previous.current;
    previous.current=view;
    const kind=animationBetween(before,view);
    if (kind && document.visibilityState === "visible" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      if(timer.current) clearTimeout(timer.current);
      setAnimation({kind,game:view.game_id,count:view.played_tricks??0});
      timer.current=setTimeout(()=>setAnimation(null),kind==="deal"?1000:650);
    }
  },[view]);
  useEffect(()=>()=>{if(timer.current) clearTimeout(timer.current);},[]);
  const active=animation&&animation.game===view.game_id&&animation.count===(view.played_tricks??0)?animation.kind:null;
  const collecting=active==="trick"&&!view.trick?.length;
  return <section data-dealing={active==="deal"?"true":undefined} className={styles.table} aria-label="Игровой стол" data-table-view="true">
    <div className={styles.tableTop}>
      <SeatAtTable view={view} seat={seats.left} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard}/>
      <CenterCards key={`${view.room_id}:${view.game_id}:${view.phase}:${view.played_tricks??0}`} view={view} collecting={collecting} onWidow={onWidow} onField={onField}/>
      <SeatAtTable view={view} seat={seats.right} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard}/>
    </div>
    {objects}
    {sharedPanel}
    <div className={styles.decision} data-table-actions="true">{actions}</div>
    <div className={styles.bottomArea}>
      <SeatAtTable view={view} seat={seats.bottom} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard}/>
      {!inLobby && view.my_seat !== null && <div className={styles.ownHand} data-own-hand="true">{hand}</div>}
      {inLobby && <p className={styles.lobbyHint}>Занято мест: {view.occupied.filter(Boolean).length} из 3</p>}
    </div>
  </section>;
}

export function PreviousTrick({view}: {view: RoomView}) {
  if (!view.last_trick?.length) return <p>Последняя взятка ещё не сыграна.</p>;
  return <div className={styles.previous} aria-label="Последняя взятка">
    {view.last_trick.map((play,i)=><div key={`${i}-${cardLabel(play.card)}`}><span>{fallbackName(play.owner)}</span><span className={styles.tableCard}><CardArtwork card={play.card}/></span></div>)}
    <small>Личный просмотр. Общий показ и пауза будут добавлены в PR13.</small>
  </div>;
}
