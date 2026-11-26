import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type DragEvent, type CSSProperties } from "react";
import { CardArtwork } from "./CardArtwork.ru";
import { bidLabel, cardId, cardLabel, type Card, type RoomView, type TableTheme } from "./game-model.ru";
import type { Presence } from "./realtime-client";
import { actorSeat, opponentCards, seatPosition, tableSeats, type Seat, type SeatProfile } from "./table-model";
import styles from "./preferans-table.module.css";
import { animationBetween, orderHand, replayWidow, visibleWidow, type SortMode } from "./interaction-model";
import { dealerFor } from "./table-interaction";
import { animateDeal, animateArrival, animateCollection, DEAL_DURATION_MS, TRICK_DURATION_MS } from "./table-motion";
import { latestTrickSeat, trickTrain, opponentWidowCards } from "./table-refinements";
import { Notebook } from "./Notebook.ru";
import { WidowDisplay } from "./WidowDisplay.ru";
import { activityProgress } from "./table-details";
import { actualTrickCount } from "./claim-model";

const positionNames = { left: "Слева", right: "Справа", bottom: "Перед собой" };
const statuses = { online: "В игре", reconnecting: "Переподключение", offline: "Отключён", unknown: "Связь неизвестна" };
const fallbackName = (seat: number) => `Игрок ${seat + 1}`;

function ActivityRing({since,now}: {since:number|undefined;now:()=>number}) {
  const [at,setAt]=useState(()=>now());
  useEffect(()=>{const timer=setInterval(()=>setAt(now()),250);return()=>clearInterval(timer);},[now,since]);
  const progress=activityProgress(since,at);
  return <svg className={styles.activityRing} viewBox="0 0 160 90" preserveAspectRatio="none" aria-hidden="true">
    {progress>0&&<path d="M3 81 V9 Q3 3 9 3 H151 Q157 3 157 9 V81 Q157 87 151 87 H9 Q3 87 3 81" pathLength="100" fill="none" stroke="currentColor" strokeWidth="3.5" strokeOpacity="0.5" strokeLinecap="round" strokeDasharray="100 100" strokeDashoffset={100-progress}/>}
  </svg>;
}

function Avatar({ seat, profile, active, presence, occupied, own, media, dealer, since, now }: {
  seat: Seat; profile?: SeatProfile; active: boolean; presence?: Presence; occupied: boolean; own: boolean; media?: ReactNode; dealer: boolean; since?:number; now:()=>number;
}) {
  const name = occupied ? profile?.name || fallbackName(seat) : "Свободное место";
  const link = occupied ? presence || "unknown" : "unknown";
  return <div className={styles.identity}>
    <div className={`${styles.avatar} ${active ? styles.activeAvatar : ""}`} title={name+(own?" (ты)":"")} aria-label={name} data-turn={active ? "true" : "false"} data-dealer={dealer?"true":undefined} data-connection={link}>
      {profile?.avatar && occupied ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={profile.avatar} alt="" width={64} height={64} draggable={false} />
      ) : <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="31" fill="#263e39"/><circle cx="32" cy="24" r="11" fill="#d5c5a2"/><path d="M12 55c1-14 10-21 20-21s19 7 20 21" fill="#d5c5a2"/></svg>}
      {media}
      {active&&<ActivityRing since={since} now={now}/>}
      {occupied && <span className={styles.connectionDot} data-presence={link} title={statuses[link]} />}
    </div>

  </div>;
}

function ThinkingClock({since,now}: {since:number|undefined;now:()=>number}) {
  const [at,setAt]=useState(()=>now());
  useEffect(()=>{const tick=()=>setAt(now());tick();const timer=setInterval(tick,250);return()=>clearInterval(timer);},[now,since]);
  const elapsed=since===undefined?null:Math.max(0,Math.floor((at-since)/1000));
  return <span className={styles.thinking}>Ждём… {elapsed===null?"":`${Math.floor(elapsed/60)}:${String(elapsed%60).padStart(2,"0")}`}</span>;
}
function TrickStack({view,seat,onReplay,busy}: {view:RoomView;seat:Seat;onReplay?:()=>void;busy:boolean}) {
  const [open,setOpen]=useState(false);
  const count=actualTrickCount(view,seat);
  const latest=latestTrickSeat(view)===seat;
  const cards=latest?view.last_trick:null;
  if(!count)return null;
  return <div className={styles.trickStackWrap} data-trick-position={seatPosition(view.my_seat,seat)??undefined} aria-label={`Взяток: ${count}`}>
    <div className={styles.trickStack} data-trick-train={seat}>
      {trickTrain(count).map(({index,turned})=><button type="button" key={index} className={styles.trickBundle} data-turned={(seatPosition(view.my_seat,seat)==="bottom"?turned:!turned)?"true":"false"} data-latest={latest&&index===count-1?"true":undefined} disabled={busy||!latest||index!==count-1} aria-label={latest&&index===count-1?"Показать последнюю взятку":"Закрытая взятка"} onClick={()=>onReplay?onReplay():setOpen(v=>!v)}><span><CardArtwork decorative/></span></button>)}
    </div>
    {open&&cards&&!onReplay&&<div className={styles.trickPreview}>{cards.map(p=><span key={p.owner}><CardArtwork card={p.card}/></span>)}<button type="button" aria-label="Закрыть взятку" onClick={()=>setOpen(false)}>×</button></div>}
  </div>;
}
function SeatAtTable({ view, seat, profiles, presence, renderOpenCard, media, deck, localControls, onSeatDrop, serverNow, sortMode, onReplay, busy, localConnected }: {
  view: RoomView; seat: Seat; profiles: SeatProfile[] | null; presence: Presence[] | null; serverNow:()=>number; sortMode:SortMode; onReplay?:()=>void; busy:boolean; localConnected:boolean;
  renderOpenCard: (card: Card, seat: Seat) => ReactNode; media?: ReactNode; deck?: ReactNode; localControls?: ReactNode; onSeatDrop?: (seat:Seat,e:DragEvent)=>void;
}) {
  const own = view.my_seat === seat;
  const position = seatPosition(view.my_seat, seat)!;
  const cards = opponentCards(view, seat);
  const active = actorSeat(view) === seat;
  const call = view.auction_calls?.[seat];
  const winning = view.winning_bid ?? (view.phase!=="auction"?view.high_bid:null);
  const speech = view.phase==="auction"&&call ? (call.kind==="pass"?"Пас":`${call.kind==="here"?"Здесь ":""}${call.bid?bidLabel(call.bid):""}`)
    : view.declarer===seat&&view.contract?(view.contract.kind==="regular"&&view.contract.level===6&&view.contract.suit==="S"?"Обязаловка":bidLabel(view.contract))
    : view.declarer===seat&&winning?bidLabel(winning)
    : view.defense?.[seat]?view.defense[seat]==="vist"?"Вист":view.defense[seat]==="half"?"Полвиста":"Пас":null;
  const opened = cards.open ? orderHand(cards.open, [], sortMode) : null;
  return <section className={`${styles.seat} ${styles[position]}`} data-seat={seat} data-position={position}
    aria-label={`${positionNames[position]}: ${profiles?.[seat]?.name || fallbackName(seat)}${own ? ", ты" : ""}`} onDragOver={e=>{if(onSeatDrop)e.preventDefault();}} onDrop={e=>onSeatDrop?.(seat,e)}>
    {speech&&<span className={styles.callBubble}>{speech}</span>}
    <div className={styles.avatarAnchor}><div className={styles.seatSignals}>{active&&<ThinkingClock since={view.activity_started_at_ms} now={serverNow}/>}</div><Avatar seat={seat} profile={profiles?.[seat]} active={active} presence={own?(localConnected?"online":"reconnecting"):presence?.[seat]} occupied={view.occupied[seat]} own={own} media={media} dealer={(dealerFor(view)??view.dealer)===seat} since={view.activity_started_at_ms} now={serverNow} />
      {view.first_hand===seat&&["playing","awaiting_settlement"].includes(view.status)&&<span className={styles.firstHand}>Первый ход</span>}
      {position!=="bottom"&&<TrickStack key={`${view.game_id}:${view.played_tricks??0}:${seat}`} view={view} seat={seat} busy={busy} onReplay={onReplay}/>}
    </div>
    {localControls}
    {deck}
    <div className={styles.seatMeta}>
      {view.revealed_cards?.filter(c=>c.seat===seat).map(c=><span key={cardId(c.card)}>Раскрыта: {cardLabel(c.card)}</span>)}
    </div>
    {!own && cards.count > 0 && !(view.claim?.status==="pending"&&view.claim.seat===seat) && <div className={`${styles.opponentHand} ${cards.open ? styles.openHand : ""}`}
      aria-label={cards.open ? `Открытая рука: ${fallbackName(seat)}` : `Закрытых карт: ${cards.count}`}>
      {opened ? opened.map((card,index) => <div className={styles.rivalCard} data-suit-break={index>0&&opened[index-1].suit!==card.suit?"true":undefined} key={cardId(card)}>{renderOpenCard(card,seat)}</div>)
        : Array.from({length:cards.count},(_,i)=><span className={styles.rivalCard} key={i} data-card-back="true"><CardArtwork decorative /></span>)}
    </div>}
  </section>;
}

function CenterCards({ view, collecting, onWidow, onField, onTableDrop, award, pendingPlay, deck, statusLine, announcement }: { statusLine:ReactNode; announcement?:ReactNode; pendingPlay?:{owner:number;card:Card}|null; view: RoomView; collecting: boolean; onWidow?: () => void; onField?: () => void; onTableDrop?: (e:DragEvent)=>void; award?: string; deck?:ReactNode }) {
  const widow = view.phase==="discard"&&!award?{count:0,cards:[]}:visibleWidow(view);
  const publicWidow = replayWidow(view);
  const [replay,setReplay] = useState(false);
  const showReplay = replay && publicWidow.length > 0;
  const opponentWidow = opponentWidowCards(view);
  const shown = collecting ? view.last_trick ?? [] : [...(view.trick ?? []), ...(pendingPlay&&!(view.trick??[]).some(p=>p.owner===pendingPlay.owner)?[pendingPlay]:[])];
  const names = tableSeats(view.my_seat);
  return <div className={styles.center}>
    {opponentWidow?<WidowDisplay cards={opponentWidow} onReplay={onWidow}/>:<div className={styles.widow} data-widow-zone="true" aria-label="Прикуп" data-award={award}>
      {widow.count > 0 && <><div className={styles.widowCards}>
        {Array.from({length:showReplay?publicWidow.length:widow.count},(_,i)=><span key={i} className={styles.tableCard}><CardArtwork card={(showReplay?publicWidow:widow.cards)[i]}/></span>)}
      </div></>}
      {widow.count === 0 && publicWidow.length > 0 && <><div className={styles.widowCards}>{Array.from({length:2},(_,i)=><span className={styles.widowGhost} key={i}>{showReplay&&publicWidow[i]&&<CardArtwork card={publicWidow[i]}/>}</span>)}</div><button type="button" className={styles.widowEye} aria-label={showReplay?"Скрыть прикуп":"Показать прикуп"} title="Показать прикуп" aria-expanded={showReplay} onClick={()=>{setReplay(v=>!v);if(onWidow&&!showReplay)onWidow();}}>◉</button></>}
    </div>}
    {deck&&<div className={styles.nextDeck} aria-label="Колода для новой раздачи">{deck}</div>}
    <div className={styles.trickField} data-play-field="true" aria-label="Текущая взятка" onDragOver={e=>{if(onTableDrop)e.preventDefault();}} onDrop={onTableDrop} data-collecting={collecting ? seatPosition(view.my_seat, view.last_trick_winner ?? -1) ?? undefined : undefined}>
      {(["left","right","bottom"] as const).map(position => {
        const played = shown.find(p=>p.owner===names[position]);
        return <div key={position} className={`${styles.trickSpot} ${styles[`trick_${position}`]}`} data-trick-seat={names[position]}>
          {played && <span className={styles.tableCard}><CardArtwork card={played.card}/></span>}
        </div>;
      })}
      <div className={styles.fieldStatus} data-has-cards={shown.length?"true":undefined} role="status" aria-live="polite">{announcement??statusLine}</div>
      {onField && <button type="button" className={styles.closeSharedField} onClick={onField}>Закрыть общий просмотр</button>}
    </div>
  </div>;
}

export function GameTable({view, profiles, presence, hand, actions, renderOpenCard, objects, onWidow, onField, sharedPanel, mediaForSeat, deck, localControls, onSeatDrop, onTableDrop, theme, serverNow, statusLine, pendingPlay, sortMode, onReplay, busy, onScore, announcement, sheetExit, surfaceOpacity, localConnected, claimPanel, claimButton, roundTable, finalReviewAction, handCount, handBreaks}: {
  view: RoomView; profiles: SeatProfile[] | null; presence: Presence[] | null;
  claimPanel?:ReactNode;claimButton?:ReactNode;roundTable:boolean;finalReviewAction?:ReactNode;handCount:number;handBreaks:number;
  theme:TableTheme;localConnected:boolean;surfaceOpacity:number;sheetExit?:ReactNode;serverNow:()=>number;statusLine:ReactNode;sortMode:SortMode;onReplay?:()=>void;onScore?:()=>void;announcement?:ReactNode;busy:boolean;pendingPlay?:{owner:number;card:Card}|null;
  hand: ReactNode; actions: ReactNode; renderOpenCard: (card: Card, seat: Seat) => ReactNode;
  objects?: ReactNode; sharedPanel?: ReactNode; onWidow?: () => void; onField?: () => void;
  mediaForSeat?: (seat: Seat) => ReactNode;
  deck?: ReactNode; localControls?: ReactNode; onSeatDrop?: (seat:Seat,e:DragEvent)=>void; onTableDrop?: (e:DragEvent)=>void;
}) {
  const seats = tableSeats(view.my_seat);
  const inLobby = view.status === "lobby";
  const between = view.status === "between";
  const [scoreOpen,setScoreOpen]=useState(false);
  const [dismissedFinal,setDismissedFinal]=useState<string|null>(null);
  const showFinal=Boolean(view.final_settlement&&dismissedFinal!==view.room_id);
  const closeScore=()=>{setScoreOpen(false);if(showFinal)setDismissedFinal(view.room_id);};
  const [localReplay,setLocalReplay]=useState<string|null>(null);
  const replayId=`${view.game_id}:${view.played_tricks}:${view.version}`;
  const replay=onReplay??(()=>setLocalReplay(replayId));
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
      timer.current=setTimeout(()=>setAnimation(null),kind==="deal"?DEAL_DURATION_MS:kind==="widow"?850:kind==="trick"?TRICK_DURATION_MS:650);
    }
    if(before?.game_id===view.game_id&&before&&view.version>before.version&&tableRef.current&&!window.matchMedia("(prefers-reduced-motion: reduce)").matches){
      const play=view.trick?.at(-1);
      if(play&&view.my_seat!==before.controller&&play.owner!==view.my_seat&&(view.trick?.length??0)>(before.trick?.length??0))animateArrival(tableRef.current,play.owner);
    }
  },[view]);
  useEffect(()=>()=>{if(timer.current) clearTimeout(timer.current);},[]);
  const active=animation&&animation.game===view.game_id&&animation.count===(view.played_tricks??0)?animation.kind:null;
  const collecting=active==="trick" && !(view.trick?.length) && !pendingPlay;
  const dealing=active==="deal";
  const animationSeat=view.last_trick_winner;
  const currentDealer=view.dealer;
  useLayoutEffect(()=>{
    const table=tableRef.current;
    if(!table)return;
    if(dealing&&currentDealer!==undefined)return animateDeal(table,currentDealer);
    if(collecting&&animationSeat!=null)return animateCollection(table,animationSeat);
  },[dealing,collecting,animationSeat,currentDealer]);
  useLayoutEffect(()=>{
    const el=tableRef.current;if(!el)return;
    const fit=()=>el.style.setProperty("--available-table-height",`${Math.max(160,(window.visualViewport?.height??window.innerHeight)-el.getBoundingClientRect().top-18)}px`);
    fit();window.addEventListener("resize",fit);document.addEventListener("fullscreenchange",fit);
    const header=document.querySelector(".preferans-site-bar");
    const observer=header&&typeof ResizeObserver!=="undefined"?new ResizeObserver(fit):null;
    if(header&&observer)observer.observe(header);
    return()=>{observer?.disconnect();window.removeEventListener("resize",fit);document.removeEventListener("fullscreenchange",fit);};
  },[inLobby]);
  return <div className={styles.tableScene}><section ref={tableRef} data-furniture={objects?"true":undefined} data-round-table={roundTable?"true":undefined} data-claim-pending={view.claim?.status==="pending"?"true":undefined} data-theme={theme==="glass"?"felt":theme} style={{"--surface-opacity":surfaceOpacity} as CSSProperties} data-holding-trick={collecting?"true":undefined} data-playing={inLobby?undefined:"true"} data-between-deals={view.status==="between"?"true":undefined} data-dealing={active==="deal"?"true":undefined} data-deck-from={active==="dealer"?animation?.from:undefined} data-local-dealer={seatPosition(view.my_seat,view.dealer??-1)??undefined} className={styles.table} aria-label="Игровой стол" data-table-view="true">
    <div className={styles.tableTop}>
      <SeatAtTable serverNow={serverNow} sortMode={sortMode} onReplay={replay} busy={busy} view={view} seat={seats.left} localConnected={localConnected} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard} media={mediaForSeat?.(seats.left)} deck={!between&&dealerFor(view)===seats.left?deck:undefined} onSeatDrop={onSeatDrop}/>
      <CenterCards statusLine={statusLine} announcement={announcement} pendingPlay={pendingPlay} key={`${view.room_id}:${view.game_id}`} deck={between?deck:undefined} view={view} collecting={collecting} onWidow={onWidow} onField={onField} onTableDrop={onTableDrop} award={active==="widow"?seatPosition(view.my_seat,view.declarer??-1)??undefined:undefined}/>
      <SeatAtTable serverNow={serverNow} sortMode={sortMode} onReplay={replay} busy={busy} view={view} seat={seats.right} localConnected={localConnected} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard} media={mediaForSeat?.(seats.right)} deck={!between&&dealerFor(view)===seats.right?deck:undefined} onSeatDrop={onSeatDrop}/>
    </div>
    {view.score&&<button type="button" className={styles.tablePaper} aria-label="Открыть пульку" title="Пулька" disabled={busy} onClick={()=>onScore?onScore():setScoreOpen(true)}>
      <Notebook view={view} profiles={profiles} miniature/>
    </button>}
    {(showFinal||(scoreOpen&&!onScore))&&view.score&&!view.presentation?.overlay&&<section className={`${styles.localDrawer} ${styles.scoreDrawer} ${styles.tableScoreDrawer}`} role="dialog" aria-label="Пулька"><Notebook view={view} profiles={profiles} reviewAction={finalReviewAction} title={view.final_review?"Проверка итоговых расчётов":view.final_settlement?"Закончили!":`${profiles?.[view.my_seat??-1]?.name||fallbackName(view.my_seat??0)} смотрит листик`} sheetExit={sheetExit} onClose={closeScore}/></section>}
    {inLobby&&objects}
    {sharedPanel}
    {claimPanel}
    {!onReplay&&localReplay===replayId&&view.last_trick?.length===3&&<section className={styles.localReplay} role="dialog" aria-label="Последняя взятка"><strong>{profiles?.[view.my_seat??-1]?.name||fallbackName(view.my_seat??0)} смотрит последнюю взятку</strong><div className={styles.localReplayCards}>{view.last_trick.map(p=><div key={p.owner}><span>{profiles?.[p.owner]?.name||fallbackName(p.owner)}</span><CardArtwork card={p.card}/></div>)}</div><button type="button" onClick={()=>setLocalReplay(null)}>Закрыть</button></section>}
    {inLobby&&<div className={styles.decision} data-table-actions="true">{actions}</div>}
    <div className={styles.bottomArea} style={{"--hand-count":handCount,"--hand-breaks":handBreaks} as CSSProperties}>
      <SeatAtTable serverNow={serverNow} sortMode={sortMode} onReplay={replay} busy={busy} view={view} seat={seats.bottom} localConnected={localConnected} profiles={profiles} presence={presence} renderOpenCard={renderOpenCard} media={mediaForSeat?.(seats.bottom)} deck={!between&&dealerFor(view)===seats.bottom?deck:undefined} onSeatDrop={onSeatDrop} localControls={localControls}/>
      {!inLobby&&<div className={styles.handColumn}>
        {view.my_seat!==null&&<TrickStack key={`${view.game_id}:${view.played_tricks??0}:${seats.bottom}`} view={view} seat={seats.bottom} busy={busy} onReplay={replay}/>}
        <div className={styles.decision} data-table-actions="true">{actions}</div>
        {claimButton&&<div className={styles.claimButton}>{claimButton}</div>}
        {view.my_seat!==null&&<div className={styles.ownHand} data-own-hand="true" data-claim-hidden={view.claim?.status==="pending"&&view.claim.seat===view.my_seat?"true":undefined}>{hand}</div>}
      </div>}
      {!inLobby&&objects&&<div className={styles.bottomFurniture} data-radio-dock="true">{objects}</div>}
      {inLobby && <p className={styles.lobbyHint}>Занято мест: {view.occupied.filter(Boolean).length} из 3</p>}
    </div>
  </section></div>;
}

export function PreviousTrick({view}: {view: RoomView}) {
  if (!view.last_trick?.length) return <p>Последняя взятка ещё не сыграна.</p>;
  return <div className={styles.previous} aria-label="Последняя взятка">
    {view.last_trick.map((play,i)=><div key={`${i}-${cardLabel(play.card)}`}><span>{fallbackName(play.owner)}</span><span className={styles.tableCard}><CardArtwork card={play.card}/></span></div>)}
    <small>Личный просмотр. Общий показ и пауза будут добавлены в PR13.</small>
  </div>;
}
