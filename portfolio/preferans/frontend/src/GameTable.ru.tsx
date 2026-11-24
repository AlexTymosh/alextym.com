import type { ReactNode } from "react";
import { CardArtwork } from "./CardArtwork.ru";
import { bidLabel, cardId, cardLabel, type Card, type RoomView } from "./game-model.ru";
import type { Presence } from "./realtime-client";
import { actorSeat, opponentCards, seatPosition, tableSeats, type Seat, type SeatProfile } from "./table-model";
import styles from "./preferans-table.module.css";

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

function CenterCards({ view }: { view: RoomView }) {
  const widow = view.widow ?? [];
  const hasDeal = view.status === "playing" || view.status === "awaiting_settlement";
  // Until PR12 only show the already-public widow; no client-side reconstruction.
  const showWidow = hasDeal && (view.phase === "auction" || widow.length > 0 || view.is_passout);
  const names = tableSeats(view.my_seat);
  return <div className={styles.center}>
    <div className={styles.widow} aria-label="Прикуп">
      {showWidow && <><span className={styles.zoneLabel}>Прикуп</span><div className={styles.widowCards}>
        {[0,1].map(i => <span key={i} className={styles.tableCard}><CardArtwork card={widow[i]} /></span>)}
      </div></>}
    </div>
    <div className={styles.trickField} aria-label="Текущая взятка">
      {(["left","right","bottom"] as const).map(position => {
        const played = view.trick?.find(p=>p.owner===names[position]);
        return <div key={position} className={`${styles.trickSpot} ${styles[`trick_${position}`]}`} data-trick-seat={names[position]}>
          {played && <span className={styles.tableCard}><CardArtwork card={played.card}/></span>}
        </div>;
      })}
      {!view.trick?.length && <span className={styles.fieldHint}>{view.status === "lobby" ? "Сбор игроков" : "Поле розыгрыша"}</span>}
    </div>
    {view.high_bid && view.phase === "auction" && <p className={styles.contract}>Торговля · {bidLabel(view.high_bid)}</p>}
    {view.contract && <p className={styles.contract}>Контракт · {bidLabel(view.contract)}</p>}
    {view.is_passout && <p className={styles.contract}>Распасы</p>}
  </div>;
}

export function GameTable({view, profiles, presence, hand, actions, renderOpenCard}: {
  view: RoomView; profiles: SeatProfile[] | null; presence: Presence[] | null;
  hand: ReactNode; actions: ReactNode; renderOpenCard: (card: Card, seat: Seat) => ReactNode;
}) {
  const seats = tableSeats(view.my_seat);
  const inLobby = view.status === "lobby";
  return <section className={styles.table} aria-label="Игровой стол" data-table-view="true">
    <div className={styles.tableTop}>
      <SeatAtTable view={view} seat={seats.left} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard}/>
      <CenterCards view={view}/>
      <SeatAtTable view={view} seat={seats.right} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard}/>
    </div>
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
