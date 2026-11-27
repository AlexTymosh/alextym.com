import { expect, test } from "@playwright/test";
import { preferansAlias, aliasChange } from "../lib/portfolio-lab/preferans-alias";
import { maySwapSeat, mayCancelCounter, notebookName } from "../../portfolio/preferans/frontend/src/room-preparation";
import { sideOpponent } from "../../portfolio/preferans/frontend/src/history-seats";
import { paperFlight } from "../../portfolio/preferans/frontend/src/paper-lift";
import type { Player } from "../../portfolio/preferans/frontend/src/history-model";
import type { RoomView } from "../../portfolio/preferans/frontend/src/game-model.ru";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

test("nickname is display-only and bounded",()=>{
  expect(preferansAlias(" Лёха ")).toBe("Лёха");
  expect(aliasChange({uid:"abc",alias:""})).toEqual({uid:"abc",alias:""});
  for(const invalid of ["a@b","a\u202eb","a".repeat(41),null])expect(preferansAlias(invalid)).toBeNull();
  expect(aliasChange({uid:"a/b",alias:"ok"})).toBeNull();
  expect(aliasChange({uid:"abc",alias:"ok",role:"Admin"})).toBeNull();
  expect(notebookName({name:"Original",avatar:null,alias:"Alias"},"fallback")).toBe("Alias");
  expect(notebookName({name:"Original",avatar:null},"fallback")).toBe("Original");
});
test("preparation uses occupied seats and only initiator or admin can cancel",()=>{
  const view={room_id:"a".repeat(32),version:3,status:"lobby",my_seat:0,occupied:[true,true,true],room_admin:false,game_id:null,lobby_setup:{ready:[false,false,false],dealer:2,target:20,ruleset:"classic",ruleset_version:1}} as RoomView;
  expect(maySwapSeat(view,1)).toBe(true);
  expect(maySwapSeat(view,0)).toBe(false);
  expect(maySwapSeat({...view,occupied:[true,true,false]},1)).toBe(false);
  expect(maySwapSeat({...view,status:"playing"},1)).toBe(false);
  const playing={...view,status:"playing",controls:{counter:{initiator:1,target:0}}} as unknown as RoomView;
  expect(mayCancelCounter(playing)).toBe(false);
  expect(mayCancelCounter({...playing,my_seat:1})).toBe(true);
  expect(mayCancelCounter({...playing,room_admin:true})).toBe(true);
  expect(mayCancelCounter({...playing,my_seat:null,room_admin:true})).toBe(false);
});
test("history seats are relative to each player and paper movement uses measured geometry",()=>{
  const players=[{id:"a",seat:0},{id:"b",seat:1},{id:"c",seat:2}] as Player[];
  for(const p of players){expect(sideOpponent(players,p.seat,"right")?.seat).toBe((p.seat+2)%3);expect(sideOpponent(players,p.seat,"left")?.seat).toBe((p.seat+1)%3);}
  expect(paperFlight({x:10,y:20,width:100,height:80},{x:100,y:200,width:500,height:400})).toEqual({x:-290,y:-340,sx:.2,sy:.2});
  expect(paperFlight({x:0,y:0,width:0,height:0},{x:0,y:0,width:1,height:1})).toBeNull();
});
test("auction and claim buttons retain opaque backgrounds on hover",async({page},info)=>{
  test.skip(info.project.name!=="chromium","Desktop hover regression");
  const base=resolve(process.cwd(),"../portfolio/preferans/frontend/src");
  const css=["preferans-game.module.css","preferans-table.module.css"].map(f=>readFileSync(resolve(base,f),"utf8")).join("\n");
  await page.setContent(`<style>${css} .table .claimPanel{position:static;transform:none;max-width:100%;width:auto;}</style><main class="root tableRoot"><section class="table"><div class="bidGroups"><button type="button" data-bid-tone="sky">Мизер</button><button type="button" disabled>6</button><span class="bidSuits"><button type="button" data-bid-tone="suit" class="redSuit"><span class="suitGlyph">♥</span></button></span></div><div class="claimPanel"><div class="claimVotes"><button>Согласен</button><button>Отказ</button></div></div></section></main>`);
  for(const name of ["Мизер","♥","Согласен","Отказ"]){const button=page.getByRole("button",{name,exact:true});await button.hover();const color=await button.evaluate(el=>getComputedStyle(el).backgroundColor);expect(color).toMatch(/^rgb\(/);}
  await expect(page.getByRole("button",{name:"6",exact:true})).toHaveCSS("opacity","0.26");
});
