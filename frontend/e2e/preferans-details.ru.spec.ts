import { expect, test } from "@playwright/test";
import { isRankingPayload, sortedRankings, type Ranking } from "../../portfolio/preferans/frontend/src/history-model";
import { mayConcede } from "../../portfolio/preferans/frontend/src/interaction-model";
import { latestTrickSeat, opponentWidowCards, WIDOW_SHOW_MS } from "../../portfolio/preferans/frontend/src/table-refinements";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

const base:RoomView={room_id:"a".repeat(32),version:2,status:"playing",my_seat:0,room_admin:true,occupied:[true,true,true],game_id:"deal",phase:"declare",declarer:0,winning_bid:{kind:"regular",level:7,suit:"H"},legal_contracts:[{kind:"regular",level:7,suit:"H"}]};
test("a defense decision precludes a concession",()=>{
  expect(mayConcede(base)).toBe(true);
  for(const decision of ["vist","pass"])expect(mayConcede({...base,defense:[null,decision,null]})).toBe(false);
  expect(mayConcede({...base,phase:"defense_first"})).toBe(false);
});
test("ranked display names are validated and sorted without changing identity",()=>{
  const rank=(id:string):Ranking=>({id,games:1,gold:0,silver:0,third:0,technical_losses:0,net_vists:0,vists_given:0,vists_received:0,timer_hill:0,bare_given:0,bare_received:0,ordinary_given:0,ordinary_received:0,total_duration_ms:0,timed_games:0,last_finished_at_ms:0});
  const a="a".repeat(24),b="b".repeat(24),rows=[rank(a),rank(b)],names={[a]:"Zed",[b]:"Alice"};
  expect(isRankingPayload({rankings:rows,player_names:names})).toBe(true);
  expect(isRankingPayload({rankings:rows,player_names:{[a]:"private@example.com"}})).toBe(false);
  expect(sortedRankings(rows,"id",false,names).map(r=>r.id)).toEqual([b,a]);
});
test("only actual latest trick is highlighted",()=>{
  const view:RoomView={...base,last_trick_winner:2,last_trick:[{owner:0,card:{suit:"H",rank:7}},{owner:1,card:{suit:"H",rank:8}},{owner:2,card:{suit:"H",rank:9}}]};
  expect(latestTrickSeat(view)).toBe(2);
  expect(latestTrickSeat({...view,last_trick:[]})).toBeNull();
});

test("only already-public normal widow cards receive the ten-second opponent display",()=>{
  const cards=[{suit:"H" as const,rank:14},{suit:"S" as const,rank:7}];
  const view:RoomView={...base,my_seat:1,phase:"discard",widow:cards};
  expect(WIDOW_SHOW_MS).toBe(10_000);
  expect(opponentWidowCards(view)).toEqual(cards);
  expect(opponentWidowCards({...view,phase:"declare"})).toEqual(cards);
  expect(opponentWidowCards({...view,phase:"defense_first"})).toEqual(cards);
  expect(opponentWidowCards({...view,my_seat:0})).toBeNull();
  expect(opponentWidowCards({...view,my_seat:null})).toBeNull();
  expect(opponentWidowCards({...view,is_passout:true})).toBeNull();
  expect(opponentWidowCards({...view,widow:cards.slice(0,1)})).toBeNull();
  expect(opponentWidowCards({...view,status:"between"})).toBeNull();
  expect(opponentWidowCards({...view,phase:"play",played_tricks:0,trick:[]})).toEqual(cards);
  expect(opponentWidowCards({...view,phase:"play",played_tricks:0,trick:[{owner:0,card:cards[0]}]})).toBeNull();
  expect(opponentWidowCards({...view,phase:"play",played_tricks:1})).toBeNull();
});
