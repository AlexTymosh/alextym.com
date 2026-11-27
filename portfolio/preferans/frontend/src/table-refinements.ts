import type { RoomView } from "./game-model.ru";
import { validSeat } from "./table-model";

export function latestTrickSeat(view: RoomView): number | null {
  return view.last_trick?.length === 3 && validSeat(view.last_trick_winner) ? view.last_trick_winner : null;
}

export function trickTrain(count: number): {index: number; turned: boolean}[] {
  if (!Number.isInteger(count) || count < 0 || count > 10) return [];
  return Array.from({length:count}, (_,index)=>({index,turned:index % 2 === 1}));
}

export const WIDOW_SHOW_MS = 10_000;
export function opponentWidowCards(view: RoomView) {
  return view.status === "playing" && !view.is_passout &&
    (view.played_tricks ?? 0) === 0 && !view.trick?.length &&
    validSeat(view.declarer) && validSeat(view.my_seat) && view.declarer !== view.my_seat &&
    view.widow?.length === 2 ? view.widow : null;
}
