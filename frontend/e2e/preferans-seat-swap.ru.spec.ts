import {test, expect} from "@playwright/test";
import {isSeatSwap} from "../../portfolio/preferans/frontend/src/seat-swap-model";
import {isRoomView} from "../../portfolio/preferans/frontend/src/game-model.ru";

const offer = {id:4, from:0, to:2, votes:[true,false,false]};
const view = {room_id:"a".repeat(32), version:4, status:"lobby", my_seat:1, occupied:[true,true,true], room_admin:false, game_id:null};
test("seat consent is typed and projected only before the first deal", () => {
  expect(isRoomView({...view, seat_swap:offer})).toBe(true);
  expect(isRoomView({...view, status:"playing", seat_swap:offer})).toBe(false);
  expect(isRoomView({...view, my_seat:null, seat_swap:offer})).toBe(false);
  expect(isRoomView({...view, seat_revision:1})).toBe(true);
  expect(isRoomView({...view, seat_revision:-1})).toBe(false);
  for (const bad of [{...offer, to:0}, {...offer, from:true}, {...offer, votes:[false,true,false]}, {...offer, votes:[true,true,true]}, {...offer, uid:"private"}]) {
    expect(isSeatSwap(bad)).toBe(false);
  }
});
