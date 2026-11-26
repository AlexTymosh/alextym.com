import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { isRoomView, type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { autoSettlementAllowed } from "../../portfolio/preferans/frontend/src/table-pr20";
const base:RoomView={room_id:"a".repeat(32),version:4,status:"awaiting_settlement",my_seat:0,room_admin:true,game_id:"deal",occupied:[true,true,true],phase:"finished",score:{pool:[20,20,20],hill:[0,0,0],vists:[[0,0,280],[10,0,10],[0,0,0]],closed:true,ruleset_hash:"hash",passout_level:6},final_review:true,final_settlement:{net:[270,20,-290],pairs:[[0,-10,280],[10,0,10],[-280,-10,0]]}};
test("final review is a valid nonterminal state and cannot auto-settle",()=>{
  expect(isRoomView(base)).toBe(true);
  expect(autoSettlementAllowed(base)).toBe(false);
  expect(isRoomView({...base,status:"closed"})).toBe(false);
  expect(isRoomView({...base,final_review:undefined})).toBe(false);
  expect(isRoomView({...base,score:{...base.score!,closed:false}})).toBe(false);
  expect(isRoomView({...base,final_review:undefined,status:"closed"})).toBe(true);
  expect(isRoomView({...base,settlement_options:{regular_choice:false,passout_defaults:["pool","pool","pool"]}})).toBe(false);
});

const root=resolve(process.cwd(),"../portfolio/preferans/frontend/src");
const read=(name:string)=>readFileSync(resolve(root,name),"utf8");
for(const [width,height,count] of [[1440,900,10],[800,450,10],[800,450,4]]) {
  test(`centred player and fixed height ${width}x${height} with ${count} cards`,async({page})=>{
    await page.setViewportSize({width,height});
    const breaks=count===10?[3,6,8]:[2];
    const cards=Array.from({length:count},(_,i)=>`<div class="cardWithSort" ${breaks.includes(i)?'data-suit-break="true"':''}><button class="playingCard" type="button"></button></div>`).join("");
    await page.setContent(`<meta name="viewport" content="width=device-width,initial-scale=1"><style>${read("preferans-game.module.css")}\n${read("preferans-table.module.css")}\n${read("preferans-shared.module.css").replace(/\.(left|right|bottom)(?![\w-])/g, ".shared_$1")}\n*{box-sizing:border-box}body{margin:0}.tableRoot{padding:0}.fixtureTile{width:100%;aspect-ratio:16/9}</style><main class="tableRoot"><section class="table" data-playing="true" data-furniture="true" data-round-table="true" style="--available-table-height:${height-25}px"><div class="tableTop"><div class="seat left"><span class="callBubble">Мизер без прикупа</span></div><div class="center"><div class="trickField" data-play-field="true"></div></div><div></div></div><div class="shared"><div class="breakPanel"><p>${"Ожидаем игроков. ".repeat(40)}</p></div></div><div class="bottomArea" style="--hand-count:${count};--hand-breaks:${breaks.length}"><div class="fixtureTile seat bottom"></div><div class="handColumn"><div class="claimButton"><button>Все мои</button></div><div class="ownHand" data-own-hand="true"><div class="handRow">${cards}</div></div></div><div class="bottomFurniture" data-radio-dock="true"><div class="objects"><button class="radioButton"><svg class="radioArt" viewBox="0 0 420 174"></svg></button></div></div></div></section></main>`);
    const d=await page.evaluate(()=>{
      const get=(s:string)=>document.querySelector(s)!.getBoundingClientRect();
      const table=get(".table"), tile=get(".fixtureTile"), hand=get(".handColumn"), card=get(".cardWithSort:last-child .playingCard"), radio=get(".radioButton"), claim=get(".claimButton button"), first=get(".cardWithSort:first-child .playingCard");
      return {height:table.height,tableMid:(table.left+table.right)/2,groupMid:(tile.left+hand.right)/2,cardRight:card.right,radioLeft:radio.left,cardBottom:card.bottom,radioBottom:radio.bottom,claimLeft:claim.left,firstLeft:first.left,bubble:getComputedStyle(document.querySelector(".callBubble")!).writingMode,field:getComputedStyle(document.querySelector(".trickField")!).borderStyle};
    });
    expect(d.height).toBeLessThanOrEqual(height-24);
    expect(Math.abs(d.tableMid-d.groupMid)).toBeLessThanOrEqual(2);
    expect(d.cardRight).toBeLessThanOrEqual(d.radioLeft+1);
    expect(Math.abs(d.cardBottom-d.radioBottom)).toBeLessThanOrEqual(2);
    expect(Math.abs(d.claimLeft-d.firstLeft)).toBeLessThanOrEqual(3);
    expect(d.bubble).toBe("horizontal-tb");
    expect(d.field).toBe("solid");
  });
}
