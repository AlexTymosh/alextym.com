import type { RoomView } from "./game-model.ru";
import { validSeat } from "./table-model";

export function latestTrickSeat(view: RoomView): number | null {
  return view.last_trick?.length === 3 && validSeat(view.last_trick_winner) ? view.last_trick_winner : null;
}

export function trickTrain(count: number): {index: number; turned: boolean}[] {
  if (!Number.isInteger(count) || count < 0 || count > 10) return [];
  return Array.from({length:count}, (_,index)=>({index,turned:index % 2 === 1}));
}
