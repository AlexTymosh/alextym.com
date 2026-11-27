import { expect,test } from "@playwright/test";
import { auctionMessage,awardedMessage } from "../../portfolio/preferans/frontend/src/play-status.ru";
import { counterTarget,counterSeconds,gagPhase,GAG_TOTAL_MS,GAG_FAKE_MS } from "../../portfolio/preferans/frontend/src/gag-model";
import { isRoomView,type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { packNotebookRows, notebookEntryLabel } from "../../portfolio/preferans/frontend/src/notebook-layout";
const base:RoomView={room_id:"a".repeat(32),version:10,game_id:"g",status:"playing",phase:"auction",my_seat:0,room_admin:false,occupied:[true,true,true],turn:1,controls:{paused:false,counter:null,undo:null,can_request_undo:false,adjustments:[]}};
const score={pool:[0,0,0],hill:[0,0,0],vists:[[0,0,0],[0,0,0],[0,0,0]],closed:false,ruleset_hash:"test",passout_level:7};
const pass={kind:"pass" as const,bid:null};
test("status follows actual auction and awarded count",()=>{
  expect(auctionMessage({...base,score})).toBe("Распасы, 7-ая");
  expect(auctionMessage({...base,score:{...score,passout_level:8}})).toBe("Распасы, 8-ная");
  expect(auctionMessage({...base,previous_passout:8,score:{...score,passout_level:6},auction_calls:[pass,pass,null]})).toBe("Чё, еще раз распасы?!");
  expect(auctionMessage({...base,previous_passout:8,auction_calls:[pass,null,null]})).toBeNull();
  expect(auctionMessage({...base,score,high_bid:{kind:"misere",level:null,suit:null}})).toBe("Ну, ты играешь 9-ную?");
  expect(auctionMessage({...base,phase:"play",score})).toBeNull();
  expect(awardedMessage({...base,claim:{seat:1,status:"accepted",voters:[0,2],approved:[0,2],rejected_by:null,awarded:6,cards:[]}},()=>"Игрок")).toBe("Игрок: +6 взяток");
});
test("counter targets actual opponent controller and freezes on pause",()=>{
  expect(counterTarget(base)).toBe(1);
  expect(counterTarget({...base,turn:0})).toBeNull();
  expect(counterTarget({...base,phase:"play",turn:1,controller:2})).toBe(2);
  expect(counterTarget({...base,phase:"misere_offer"})).toBeNull();
  expect(counterTarget({...base,controls:{...base.controls!,paused:true}})).toBeNull();
  expect(counterSeconds(181000,undefined,1000)).toBe(180);
  expect(counterSeconds(181000,undefined,181001)).toBe(0);
  expect(counterSeconds(null,9700,100000)).toBe(10);
});
test("joke is time-bounded, private projections contain no cards",()=>{
  const mark={seat:2,at_ms:1000};
  expect(gagPhase(mark,1000)).toBe("fake");
  expect(gagPhase(mark,1000+GAG_FAKE_MS-1)).toBe("fake");
  expect(gagPhase(mark,1000+GAG_FAKE_MS)).toBe("deal");
  expect(gagPhase(mark,1000+GAG_TOTAL_MS)).toBeNull();
  expect(isRoomView({...base,redeal_gag:mark,server_clock_ms:1000})).toBe(true);
  expect(isRoomView({...base,redeal_gag:{...mark,cards:[]}})).toBe(false);
  expect(isRoomView({...base,redeal_gag:mark,my_seat:null})).toBe(false);
  expect(isRoomView({...base,redeal_gag:mark,phase:"play"})).toBe(false);
  expect(isRoomView({...base,previous_passout:9})).toBe(false);
});
test("wider hill line keeps more entries and preserves order",()=>{
  const tokens=[3,17,35,37,39,42].map((n,i)=>({label:notebookEntryLabel(String(n)),latest:i===5}));
  expect(packNotebookRows(tokens,176).length).toBeGreaterThan(1);
  expect(packNotebookRows(tokens,232)).toEqual([tokens]);
});
