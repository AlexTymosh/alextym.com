import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type DragEvent } from "react";
import { CardArtwork } from "./CardArtwork.ru";
import { bidLabel, cardId, cardLabel, type Card, type RoomView, type TableTheme } from "./game-model.ru";
import type { Presence } from "./realtime-client";
import { actorSeat, opponentCards, seatPosition, tableSeats, type Seat, type SeatProfile } from "./table-model";
import styles from "./preferans-table.module.css";
import { animationBetween, replayWidow, visibleWidow } from "./interaction-model";
import { dealerFor } from "./table-interaction";
import { animateDeal, animateArrival } from "./table-motion";

const positionNames = { left: "Слева", right: "Справа", bottom: "Перед собой" };
const statuses = { online: "В игре", reconnecting: "Переподключение", offline: "Отключён", unknown: "Связь неизвестна" };
const fallbackName = (seat: number) => `Игрок ${seat + 1}`;

function Avatar({ seat, profile, active, presence, occupied, own, media }: {
  seat: Seat; profile?: SeatProfile; active: boolean; presence?: Presence; occupied: boolean; own: boolean; media?: ReactNode;
}) {
  const name = occupied ? profile?.name || fallbackName(seat) : "Свободное место";
  const link = occupied ? presence || "unknown" : "unknown";
  return <div className={styles.identity}>
    <div className={`${styles.avatar} ${active ? styles.activeAvatar : ""}`} data-turn={active ? "true" : "false"}>
      {profile?.avatar && occupied ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={profile.avatar} alt="" width={64} height={64} draggable={false} />
      ) : <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="31" fill="#263e39"/><circle cx="32" cy="24" r="11" fill="#d5c5a2"/><path d="M12 55c1-14 10-21 20-21s19 7 20 21" fill="#d5c5a2"/></svg>}
      {media}
      {occupied && <span className={styles.connectionDot} data-presence={link} title={statuses[link]} />}
    </div>
    <div className={styles.identityText}><strong title={name}>{name}{own ? " (ты)" : ""}</strong>
      {occupied && <span className={styles.connectionText}>{statuses[link]}{active ? " · Ходит" : ""}</span>}
    </div>
  </div>;
}

function ThinkingClock({since,now}: {since:number|undefined;now:()=>number}) {
  const [at,setAt]=useState(()=>now());
  useEffect(()=>{const tick=()=>setAt(now());tick();const timer=setInterval(tick,250);return()=>clearInterval(timer);},[now,since]);
  const elapsed=since===undefined?null:Math.max(0,Math.floor((at-since)/1000));
  return <span className={styles.thinking}>Ждём… {elapsed===null?"":`${Math.floor(elapsed/60)}:${String(elapsed%60).padStart(2,"0")}`}</span>;
}
function TrickStack({view,seat}: {view:RoomView;seat:Seat}) {
  const [open,setOpen]=useState(false);
  const count=view.tricks_won?.[seat]??0;
  const cards=view.last_won_tricks?.[seat];
  if(!count)return null;
  return <div className={styles.trickStackWrap}><button type="button" className={styles.trickStack} aria-label={`Взятки: ${count}. Последняя взятка игрока ${seat+1}`} aria-expanded={open} disabled={!cards} onClick={()=>setOpen(v=>!v)}>
    {Array.from({length:Math.min(count,10)},(_,i)=><span key={i} style={{transform:`translate(${i*2}px,${-i*2}px) rotate(${i%2?90:0}deg)`}}><CardArtwork decorative/></span>)}<b>{count}</b></button>
    {open&&cards&&<div className={styles.trickPreview}>{cards.map(p=><span key={p.owner}><CardArtwork card={p.card}/></span>)}<button type="button" aria-label="Закрыть взятку" onClick={()=>setOpen(false)}>×</button></div>}</div>;
}
function SeatAtTable({ view, seat, profiles, presence, renderOpenCard, media, deck, localControls, onSeatDrop, serverNow }: {
  view: RoomView; seat: Seat; profiles: SeatProfile[] | null; presence: Presence[] | null; serverNow:()=>number;
  renderOpenCard: (card: Card, seat: Seat) => ReactNode; media?: ReactNode; deck?: ReactNode; localControls?: ReactNode; onSeatDrop?: (seat:Seat,e:DragEvent)=>void;
}) {
  const own = view.my_seat === seat;
  const position = seatPosition(view.my_seat, seat)!;
  const cards = opponentCards(view, seat);
  const active = actorSeat(view) === seat;
  return <section className={`${styles.seat} ${styles[position]}`} data-seat={seat} data-position={position}
    aria-label={`${positionNames[position]}: ${profiles?.[seat]?.name || fallbackName(seat)}${own ? ", ты" : ""}`} onDragOver={e=>{if(onSeatDrop)e.preventDefault();}} onDrop={e=>onSeatDrop?.(seat,e)}>
    {active&&<ThinkingClock since={view.activity_started_at_ms} now={serverNow}/>}
    <Avatar seat={seat} profile={profiles?.[seat]} active={active} presence={presence?.[seat]} occupied={view.occupied[seat]} own={own} media={media} />
    {localControls}
    {deck}
    <div className={styles.seatMeta}>
      {view.phase === "auction" && view.auction_calls?.[seat] && <span className={styles.callBubble}>
        {view.auction_calls[seat]?.kind === "pass" ? "ПАС" : `${view.auction_calls[seat]?.kind === "here" ? "Здесь " : ""}${view.auction_calls[seat]?.bid ? bidLabel(view.auction_calls[seat]!.bid!) : ""}`}
      </span>}
      {view.defense?.[seat] && ["defense_first","defense_second","defense_reconsider","choose_mode","opening_lead","play"].includes(view.phase ?? "") && <span className={styles.callBubble}>{view.defense[seat]==="vist"?"Вист":view.defense[seat]==="half"?"Полвиста":"Пас"}</span>}
      {(dealerFor(view)??view.dealer) === seat && <span>Сдаёт</span>}
      {view.declarer === seat && <span>Заказчик</span>}
      <TrickStack key={`${view.game_id}:${seat}`} view={view} seat={seat}/>
      {view.revealed_cards?.filter(c=>c.seat===seat).map(c=><span key={cardId(c.card)}>Раскрыта: {cardLabel(c.card)}</span>)}
    </div>
    {!own && cards.count > 0 && <div className={`${styles.opponentHand} ${cards.open ? styles.openHand : ""}`}
      aria-label={cards.open ? `Открытая рука: ${fallbackName(seat)}` : `Закрытых карт: ${cards.count}`}>
      {cards.open ? cards.open.map(card => <div className={styles.rivalCard} key={cardId(card)}>{renderOpenCard(card,seat)}</div>)
        : Array.from({length:cards.count},(_,i)=><span className={styles.rivalCard} key={i} data-card-back="true"><CardArtwork decorative /></span>)}
    </div>}
  </section>;
}

function CenterCards({ view, collecting, onWidow, onField, onTableDrop, award, pendingPlay }: { pendingPlay?:{owner:number;card:Card}|null; view: RoomView; collecting: boolean; onWidow?: () => void; onField?: () => void; onTableDrop?: (e:DragEvent)=>void; award?: string }) {
  const widow = view.phase==="discard"&&!award?{count:0,cards:[]}:visibleWidow(view);
  const publicWidow = replayWidow(view);
  const [replay,setReplay] = useState(false);
  const showReplay = replay && publicWidow.length > 0;
  const shown = collecting ? view.last_trick ?? [] : [...(view.trick ?? []), ...(pendingPlay&&!(view.trick??[]).some(p=>p.owner===pendingPlay.owner)?[pendingPlay]:[])];
  const names = tableSeats(view.my_seat);
  return <div className={styles.center}>
    <div className={styles.widow} data-widow-zone="true" aria-label="Прикуп" data-award={award}>
      {widow.count > 0 && <><span className={styles.zoneLabel}>Прикуп</span><div className={styles.widowCards}>
        {Array.from({length:showReplay?publicWidow.length:widow.count},(_,i)=><span key={i} className={styles.tableCard}><CardArtwork card={(showReplay?publicWidow:widow.cards)[i]}/></span>)}
      </div></>}
      {widow.count === 0 && publicWidow.length > 0 && <><div className={styles.widowCards}>{Array.from({length:2},(_,i)=><span className={styles.widowGhost} key={i}>{showReplay&&publicWidow[i]&&<CardArtwork card={publicWidow[i]}/>}</span>)}</div><button type="button" className={styles.widowEye} aria-label={showReplay?"Скрыть прикуп":"Показать прикуп"} title="Показать прикуп" aria-expanded={showReplay} onClick={()=>{setReplay(v=>!v);if(onWidow&&!showReplay)onWidow();}}>◉</button></>}
    </div>
    <div className={styles.trickField} aria-label="Текущая взятка" onDragOver={e=>{if(onTableDrop)e.preventDefault();}} onDrop={onTableDrop} data-collecting={collecting ? seatPosition(view.my_seat, view.last_trick_winner ?? -1) ?? undefined : undefined}>
      {(["left","right","bottom"] as const).map(position => {
        const played = shown.find(p=>p.owner===names[position]);
        return <div key={position} className={`${styles.trickSpot} ${styles[`trick_${position}`]}`} data-trick-seat={names[position]}>
          {played && <span className={styles.tableCard}><CardArtwork card={played.card}/></span>}
        </div>;
      })}
      {!shown.length && <span className={styles.fieldHint}>{view.status === "lobby" ? "Сбор игроков" : "Поле розыгрыша"}</span>}
      {onField && <button type="button" className={styles.closeSharedField} onClick={onField}>Закрыть общий просмотр</button>}
    </div>
    {view.contract && <p className={styles.contract}>Контракт · {bidLabel(view.contract)}</p>}
    {view.contract?.kind === "regular" && view.contract.level === 6 && view.contract.suit === "S" && <p className={styles.contract}>Обязаловка</p>}
    {view.is_passout && <p className={styles.contract}>Распасы</p>}
  </div>;
}

export function GameTable({view, profiles, presence, hand, actions, renderOpenCard, objects, onWidow, onField, sharedPanel, mediaForSeat, deck, localControls, onSeatDrop, onTableDrop, theme, serverNow, statusLine, pendingPlay}: {
  view: RoomView; profiles: SeatProfile[] | null; presence: Presence[] | null;
  theme:TableTheme;serverNow:()=>number;statusLine:string;pendingPlay?:{owner:number;card:Card}|null;
  hand: ReactNode; actions: ReactNode; renderOpenCard: (card: Card, seat: Seat) => ReactNode;
  objects?: ReactNode; sharedPanel?: ReactNode; onWidow?: () => void; onField?: () => void;
  mediaForSeat?: (seat: Seat) => ReactNode;
  deck?: ReactNode; localControls?: ReactNode; onSeatDrop?: (seat:Seat,e:DragEvent)=>void; onTableDrop?: (e:DragEvent)=>void;
}) {
  const seats = tableSeats(view.my_seat);
  const inLobby = view.status === "lobby";
  const previous = useRef<RoomView|null>(null);
  const tableRef=useRef<HTMLElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const [animation,setAnimation] = useState<{kind:"deal"|"trick"|"widow"|"dealer";game:string|null;count:number;from?:string}|null>(null);
  useLayoutEffect(()=>{
    const before=previous.current;
    previous.current=view;
    const kind=before?.room_id===view.room_id&&before?.status==="lobby"&&view.status==="lobby"&&before.lobby_setup&&view.lobby_setup&&before.lobby_setup.dealer!==view.lobby_setup.dealer?"dealer":before?.game_id===view.game_id&&before?.phase==="auction"&&view.phase==="discard"?"widow":animationBetween(before,view);
    if (kind && document.visibilityState === "visible" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      if(timer.current) clearTimeout(timer.current);
      setAnimation({kind,game:view.game_id,count:view.played_tricks??0,from:kind==="dealer"?seatPosition(view.my_seat,before?.lobby_setup?.dealer??-1)??undefined:undefined});
      timer.current=setTimeout(()=>setAnimation(null),kind==="deal"?1100:kind==="widow"?850:kind==="trick"?1300:650);
      if(kind==="deal"&&tableRef.current&&view.dealer!==undefined)animateDeal(tableRef.current,view.dealer);
    }
    if(before?.game_id===view.game_id&&before&&view.version>before.version&&tableRef.current&&!window.matchMedia("(prefers-reduced-motion: reduce)").matches){
      const play=view.trick?.at(-1);
      if(play&&view.my_seat!==before.controller&&play.owner!==view.my_seat&&(view.trick?.length??0)>(before.trick?.length??0))animateArrival(tableRef.current,play.owner);
    }
  },[view]);
  useEffect(()=>()=>{if(timer.current) clearTimeout(timer.current);},[]);
  const active=animation&&animation.game===view.game_id&&animation.count===(view.played_tricks??0)?animation.kind:null;
  const collecting=active==="trick";
  useLayoutEffect(()=>{
    const el=tableRef.current;if(!el)return;
    const fit=()=>el.style.setProperty("--available-table-height",`${Math.max(220,window.innerHeight-el.getBoundingClientRect().top-34)}px`);
    fit();window.addEventListener("resize",fit);document.addEventListener("fullscreenchange",fit);
    return()=>{window.removeEventListener("resize",fit);document.removeEventListener("fullscreenchange",fit);};
  },[inLobby]);
  return <div className={styles.tableScene}><section ref={tableRef} data-theme={theme} data-holding-trick={collecting?"true":undefined} onKeyDownCapture={e=>{if(collecting&&e.target instanceof HTMLElement&&e.target.closest("[data-card]")&&(e.key==="Enter"||e.key===" ")){e.preventDefault();e.stopPropagation();}}} data-playing={inLobby?undefined:"true"} data-dealing={active==="deal"?"true":undefined} data-deck-from={active==="dealer"?animation?.from:undefined} data-local-dealer={seatPosition(view.my_seat,view.dealer??-1)??undefined} className={styles.table} aria-label="Игровой стол" data-table-view="true">
    <div className={styles.tableTop}>
      <SeatAtTable serverNow={serverNow} view={view} seat={seats.left} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard} media={mediaForSeat?.(seats.left)} deck={dealerFor(view)===seats.left?deck:undefined} onSeatDrop={onSeatDrop}/>
      <CenterCards pendingPlay={pendingPlay} key={`${view.room_id}:${view.game_id}:${view.phase}`} view={view} collecting={collecting} onWidow={onWidow} onField={onField} onTableDrop={collecting?undefined:onTableDrop} award={active==="widow"?seatPosition(view.my_seat,view.declarer??-1)??undefined:undefined}/>
      <SeatAtTable serverNow={serverNow} view={view} seat={seats.right} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard} media={mediaForSeat?.(seats.right)} deck={dealerFor(view)===seats.right?deck:undefined} onSeatDrop={onSeatDrop}/>
    </div>
    {objects}
    {sharedPanel}
    <div className={styles.decision} data-table-actions="true">{actions}</div>
    <div className={styles.bottomArea}>
      <SeatAtTable serverNow={serverNow} view={view} seat={seats.bottom} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard} media={mediaForSeat?.(seats.bottom)} deck={dealerFor(view)===seats.bottom?deck:undefined} onSeatDrop={onSeatDrop} localControls={localControls}/>
      {!inLobby && view.my_seat !== null && <div className={styles.ownHand} data-own-hand="true">{hand}</div>}
      {inLobby && <p className={styles.lobbyHint}>Занято мест: {view.occupied.filter(Boolean).length} из 3</p>}
    </div>
  </section><div role="status" className={styles.statusLine}>{statusLine}</div></div>;
}

export function PreviousTrick({view}: {view: RoomView}) {
  if (!view.last_trick?.length) return <p>Последняя взятка ещё не сыграна.</p>;
  return <div className={styles.previous} aria-label="Последняя взятка">
    {view.last_trick.map((play,i)=><div key={`${i}-${cardLabel(play.card)}`}><span>{fallbackName(play.owner)}</span><span className={styles.tableCard}><CardArtwork card={play.card}/></span></div>)}
    <small>Личный просмотр. Общий показ и пауза будут добавлены в PR13.</small>
  </div>;
}
