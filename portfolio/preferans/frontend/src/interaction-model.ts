import type { Bid, Card, RoomView } from "./game-model.ru";

export type BidGroup = "6" | "7" | "8" | "9" | "10" | "misere" | "misere_no_widow" | "ten_no_widow";
export const BID_GROUPS: BidGroup[] = ["6", "7", "8", "9", "10", "misere", "misere_no_widow", "ten_no_widow"];
export const bidGroup = (bid: Bid): BidGroup => bid.kind === "regular" ? String(bid.level) as BidGroup : bid.kind;
export function bidsInGroup(bids: readonly Bid[], group: BidGroup): Bid[] {
  return bids.filter(bid => bidGroup(bid) === group);
}
export function canHold(view: RoomView): boolean {
  return view.phase === "auction" && view.can_say_here === true && !!view.high_bid &&
    view.high_bid.kind !== "misere" && view.high_bid.kind !== "misere_no_widow" &&
    !(view.high_bid.kind === "regular" && view.high_bid.level === 6 && view.high_bid.suit === "S");
}
export type SortMode = "grouped" | "suit";
const id = (card: Card) => `${card.rank}${card.suit}`;
const suits = "SCDH";
export function orderHand(cards: readonly Card[], manual: readonly string[] = [], mode: SortMode = "grouped"): Card[] {
  const groups = new Map<string, Card[]>();
  for (const card of cards) groups.set(card.suit, [...(groups.get(card.suit) ?? []), card]);
  const groupList = Array.from(groups.values()).map(group => group.sort((a,b) => b.rank-a.rank));
  groupList.sort((a,b) => (mode === "grouped" ? b.length-a.length || b[0].rank-a[0].rank : 0) || suits.indexOf(a[0].suit)-suits.indexOf(b[0].suit));
  const sorted = groupList.flat();
  const byId = new Map(sorted.map(card => [id(card), card]));
  const result: Card[] = [];
  for (const key of manual) {
    const card = byId.get(key);
    if (card) { result.push(card); byId.delete(key); }
  }
  return [...result, ...Array.from(byId.values())];
}
export function ownCards(view: RoomView | null): Card[] {
  if (!view || view.my_seat === null) return [];
  const cards = [...(view.hand ?? [])];
  if (view.phase === "discard" && view.my_seat === view.declarer) {
    for (const card of view.widow ?? []) if (!cards.some(existing => id(existing) === id(card))) cards.push(card);
  }
  return cards;
}
export function visibleWidow(view: RoomView): { count: number; cards: Card[] } {
  if (view.status !== "playing") return {count:0,cards:[]};
  if (view.phase === "auction") return {count:2,cards:[]};
  if (view.phase === "discard") return {count:Math.min(2,view.widow?.length ?? 0),cards:(view.widow ?? []).slice(0,2)};
  if (view.is_passout && (view.played_tricks ?? 0) < 2) {
    const index=view.played_tricks ?? 0;
    return {count:index===0?2:1,cards:(view.widow ?? []).slice(index,index+1)};
  }
  return {count:0,cards:[]};
}
/** During collection, retain the passout widow as it looked before this trick. */
export function passoutWidowFrame(view:RoomView, collecting:boolean):{view:RoomView;held:boolean} {
  const count=view.played_tricks??0;
  if(!collecting||!view.is_passout||count<1||count>2)return {view,held:false};
  return {view:{...view,played_tricks:count-1,widow:(view.widow??[]).slice(0,count)},held:true};
}
export function replayWidow(view: RoomView): Card[] {
  return (view.widow ?? []).slice(0,2);
}
export type DealAnimation = "deal" | "trick" | null;
export function animationBetween(previous: RoomView | null, current: RoomView): DealAnimation {
  if (!previous || previous.room_id !== current.room_id || current.version <= previous.version) return null;
  if (previous.game_id !== current.game_id && ["lobby","between"].includes(previous.status) && current.phase === "auction" && current.status === "playing") return "deal";
  if (previous.game_id && previous.game_id === current.game_id &&
      (current.played_tricks ?? 0) === (previous.played_tricks ?? 0)+1 &&
      current.last_trick?.length === 3 &&
      [0,1,2].includes(current.last_trick_winner ?? -1)) return "trick";
  return null;
}
export function mayConcede(view: RoomView): boolean {
  return view.status === "playing" && view.phase === "declare" && view.my_seat !== null && view.declarer === view.my_seat &&
    !view.controls?.paused && !view.controls?.undo &&
    (view.legal_contracts ?? []).some(bid => bid.kind === "regular" || bid.kind === "ten_no_widow") &&
    !view.defense?.some(Boolean) && (view.played_tricks ?? 0) === 0 && (view.trick?.length ?? 0) === 0;
}
