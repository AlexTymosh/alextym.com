import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { latestTrickSeat, trickTrain } from "../../portfolio/preferans/frontend/src/table-refinements";
import { ruleTopics } from "../../portfolio/preferans/frontend/src/rules-faq";
import source from "../../portfolio/preferans/frontend/src/rules-source.ru.json";
import { isRoomView, type RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";

const base:RoomView={room_id:"a".repeat(32),version:1,status:"playing",my_seat:0,room_admin:true,game_id:"deal",occupied:[true,true,true]};
test("only the globally latest trick is replayable, not per-player history",()=>{
  expect(latestTrickSeat(base)).toBeNull();
  const last:RoomView={...base,last_trick_winner:1,last_trick:[{owner:0,card:{suit:"H",rank:7}},{owner:1,card:{suit:"H",rank:14}},{owner:2,card:{suit:"H",rank:9}}],tricks_won:[4,1,2]};
  expect(latestTrickSeat(last)).toBe(1);
  expect(latestTrickSeat({...last,last_trick_winner:2,last_trick:[]})).toBeNull();
  expect(trickTrain(4)).toEqual([{index:0,turned:false},{index:1,turned:true},{index:2,turned:false},{index:3,turned:true}]);
  expect(trickTrain(11)).toEqual([]);
});
test("FAQ preserves the authoritative documents and all numbered questions",()=>{
  const read=(name:string)=>readFileSync(resolve(process.cwd(),`../portfolio/preferans/docs/${name}`),"utf8").replace(/\r\n/g,"\n");
  expect(source.rules).toBe(read("HOUSE_RULES.ru.md"));
  expect(source.decisions).toBe(read("HOUSE_RULES_DECISIONS.ru.md"));
  const topics=ruleTopics(source.rules);
  expect(topics.length).toBeGreaterThanOrEqual(15);
  expect(topics.flatMap(t=>t.questions).length).toBeGreaterThan(80);
  expect(topics.flatMap(t=>t.questions).find(q=>q.title.startsWith("4.6."))?.body).toContain("Более ранние взятки не открываются.");
  expect(ruleTopics(source.decisions).filter(t=>t.title.startsWith("Решение"))).toHaveLength(3);
});

test("winning bid is optional during a rolling deployment and validated when provided",()=>{
  expect(isRoomView(base)).toBe(true);
  expect(isRoomView({...base,winning_bid:{kind:"regular",level:7,suit:"D"}})).toBe(true);
  expect(isRoomView({...base,winning_bid:{kind:"regular",level:12,suit:"D"}})).toBe(false);
});
