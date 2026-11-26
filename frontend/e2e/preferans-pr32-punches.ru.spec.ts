import { expect, test } from "@playwright/test";
import { misereOfferCards } from "../../portfolio/preferans/frontend/src/interaction-model";
import { isRoomView, allowedToAct, type RoomView, type Card } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { isNotebookPunches, punchGeometry, type NotebookPunch } from "../../portfolio/preferans/frontend/src/notebook-punches";
import { tableSeats } from "../../portfolio/preferans/frontend/src/table-model";

const base:RoomView={room_id:"a".repeat(32),version:1,status:"playing",my_seat:0,room_admin:false,game_id:"deal",occupied:[true,true,true],phase:"misere_offer",declarer:0,misere_offer:{approved:[],can_vote:false}};
const hand:Card[]=[{suit:"H",rank:7},{suit:"C",rank:8},{suit:"S",rank:9},{suit:"H",rank:14},{suit:"C",rank:12}];
const grouped:Card[]=[hand[3],hand[0],hand[4],hand[1],hand[2]];
const suit:Card[]=[hand[2],hand[4],hand[1],hand[3],hand[0]];

test("each viewer sorts only the declarer's visible offer by local preference",()=>{
  const original=JSON.stringify(hand);
  for(const my_seat of [0,1,2]){
    const view:RoomView={...base,my_seat,hand:my_seat===0?hand:[{suit:"D",rank:14}],open_hands:my_seat===0?[]:[{seat:0,cards:hand}],misere_offer:{approved:[],can_vote:my_seat!==0}};
    expect(misereOfferCards(view,"grouped")).toEqual(grouped);
    expect(misereOfferCards(view,"suit")).toEqual(suit);
  }
  expect(misereOfferCards({...base,my_seat:1,hand,open_hands:[]},"grouped")).toEqual([]);
  expect(misereOfferCards({...base,my_seat:null,hand},"grouped")).toEqual([]);
  expect(JSON.stringify(hand)).toBe(original);
});

test("both defenders may independently approve, but neither can vote twice",()=>{
  for(const declarer of [0,1,2])for(const my_seat of [0,1,2]){
    const defenders=[0,1,2].filter(n=>n!==declarer);
    for(const approved of [[],[defenders[0]],[defenders[1]]]){
      const can_vote=my_seat!==declarer&&!approved.includes(my_seat);
      const view:RoomView={...base,my_seat,declarer,turn:defenders.find(n=>!approved.includes(n)),misere_offer:{approved,can_vote}};
      expect(isRoomView(view)).toBe(true);
      expect(allowedToAct(view)).toBe(can_vote);
    }
  }
});

const awards:NotebookPunch[]=[{from:1,to:0,bare:0,ordinary:2},{from:2,to:0,bare:0,ordinary:3},{from:2,to:1,bare:0,ordinary:1}];
const net=[-61,12,49];
test("final award wire validation rejects forged direction, duplicate pairs and non-final state",()=>{
  const final:RoomView={...base,phase:"finished",status:"closed",misere_offer:undefined,final_settlement:{net,pairs:[[0,-27,-34],[27,0,-15],[34,15,0]]},final_punches:awards};
  expect(isRoomView(final)).toBe(true);
  expect(isRoomView({...final,final_punches:[{...awards[0],from:0,to:1}]})).toBe(false);
  expect(isRoomView({...final,final_punches:[awards[0],awards[0]]})).toBe(false);
  expect(isRoomView({...final,final_punches:[{...awards[0],ordinary:0}]})).toBe(false);
  expect(isRoomView({...final,final_settlement:undefined})).toBe(false);
  expect(isRoomView({...final,status:"playing"})).toBe(false);
  expect(isRoomView({...final,final_punches:undefined})).toBe(true);
  expect(isNotebookPunches([],net)).toBe(true);
  expect(isNotebookPunches([{from:2,to:0,bare:1,ordinary:5}],net)).toBe(true);
});

test("all seat rotations and both arrow directions follow winner and loser sectors",()=>{
  for(const origin of [0,1,2]){
    const seats=tableSeats(origin);
    const {left,right,bottom}=seats;
    for(const [from,to] of [[left,right],[right,left],[left,bottom],[bottom,left],[right,bottom],[bottom,right]]){
      const award={from,to,bare:0,ordinary:1};
      for(const [w,cy,inner,innerY] of [[732,322,156,556],[1100,650,310,910]]){
        const g=punchGeometry(award,seats,w,cy,inner,innerY);
        const reverse=punchGeometry({...award,from:to,to:from},seats,w,cy,inner,innerY);
        expect(g.start).toEqual(reverse.end);expect(g.end).toEqual(reverse.start);
        expect(g.center).toEqual(reverse.center);
        if(to===bottom)expect(g.end.y).toBeGreaterThan(g.start.y);
        else if(from===bottom)expect(g.end.y).toBeLessThan(g.start.y);
        else expect(g.end.x>g.start.x).toBe(to===right);
        for(const p of [g.start,g.end]){expect(p.x).toBeGreaterThan(0);expect(p.x).toBeLessThan(w);expect(p.y).toBeGreaterThan(0);expect(p.y).toBeLessThan(innerY);}
      }
    }
  }
});
