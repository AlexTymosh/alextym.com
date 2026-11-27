import type { RoomView } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
export function maySwapSeat(view:RoomView,seat:number):boolean {
  return view.status==="lobby"&&!!view.lobby_setup&&view.my_seat!==null&&[0,1,2].includes(seat)&&seat!==view.my_seat&&view.occupied.every(Boolean)&&!view.seat_swap;
}
export function mayCancelCounter(view:RoomView):boolean {
  return view.status==="playing"&&view.my_seat!==null&&!!view.controls?.counter&&(view.room_admin||view.controls.counter.initiator===view.my_seat);
}
export function notebookName(profile:SeatProfile|undefined,fallback:string):string {
  return profile?.alias||profile?.name||fallback;
}
