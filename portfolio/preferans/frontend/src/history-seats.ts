import type { Player } from "./history-model";
/** The same clockwise order as tableSeats: +1 left, +2 right. */
export function sideOpponent(players:readonly Player[],seat:number,side:"left"|"right"):Player|undefined {
  if(![0,1,2].includes(seat))return undefined;
  return players.find(p=>p.seat===(seat+(side==="left"?1:2))%3);
}
