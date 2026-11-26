import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root=resolve(process.cwd(),"../portfolio/preferans/frontend/src");
const read=(file:string)=>readFileSync(resolve(root,file),"utf8");
const table=read("preferans-table.module.css");
const shared=read("preferans-shared.module.css");
const game=read("preferans-game.module.css");
const notebook=read("preferans-notebook.module.css");

// CSS regression fixtures exercise the actual stylesheets, not the authenticated room.
for(const [width,height] of [[1440,900],[800,450]]){
  test(`bottom dock and compact radio do not overlap at ${width}x${height}`,async({page})=>{
    await page.setViewportSize({width,height});
    const cards=Array.from({length:12},(_,i)=>`<div class="cardWithSort" ${[3,6,9].includes(i)?'data-suit-break="true"':''}><button class="playingCard" type="button"></button></div>`).join("");
    await page.setContent(`<meta name="viewport" content="width=device-width, initial-scale=1"><style>${game}\n${table}\n${shared}\n*{box-sizing:border-box}body{margin:0} .tableRoot{padding:0}.fixtureTile{width:100%;aspect-ratio:16/9}</style>
      <main class="tableRoot"><section class="table" data-playing="true" data-furniture="true" style="--available-table-height:${height-25}px">
        <div class="tableTop"></div><div class="bottomArea"><div class="fixtureTile"></div><div class="handColumn"><div class="ownHand" data-own-hand="true"><div class="handRow">${cards}</div></div></div><div class="bottomFurniture" data-radio-dock="true"><div class="objects"><button class="radioButton" type="button"><svg class="radioArt" viewBox="0 0 420 174"></svg></button></div></div></div>
        <section class="panel radioOverlay" role="dialog"><header>Radio</header><div class="radio"><svg class="radioArt" viewBox="0 0 420 174"></svg></div></section>
      </section></main>`);
    const dimensions=await page.evaluate(()=>{
      const get=(selector:string)=>document.querySelector(selector)!.getBoundingClientRect();
      const table=get(".table"), row=get(".bottomArea"), card=get(".cardWithSort:last-child .playingCard"), radio=get(".radioButton"), dialog=get(".radioOverlay");
      return {padding:getComputedStyle(document.querySelector(".bottomArea")!).paddingBottom,cardBottom:card.bottom,radioBottom:radio.bottom,cardRight:card.right,radioLeft:radio.left,rowBottom:row.bottom,tableBottom:table.bottom,tableWidth:table.width,dialogWidth:dialog.width,dialogPosition:getComputedStyle(document.querySelector(".radioOverlay")!).position};
    });
    expect(dimensions.padding).toBe("0px");
    expect(Math.abs(dimensions.cardBottom-dimensions.radioBottom)).toBeLessThanOrEqual(2);
    expect(dimensions.cardRight).toBeLessThanOrEqual(dimensions.radioLeft+1);
    expect(dimensions.tableBottom-dimensions.rowBottom).toBeLessThan(45);
    expect(dimensions.tableBottom).toBeLessThanOrEqual(height+1);
    expect(dimensions.dialogPosition).toBe("absolute");
    expect(dimensions.dialogWidth).toBeLessThanOrEqual(420);
    expect(dimensions.dialogWidth).toBeLessThan(dimensions.tableWidth);
  });
}

test("notebook toolbar is compact and preserves labelled close and rotation actions",async({page})=>{
  await page.setViewportSize({width:1280,height:800});
  await page.setContent(`<meta name="viewport" content="width=device-width,initial-scale=1"><style>${notebook}\n*{box-sizing:border-box}</style><div class="wrap" style="--paper-ratio:0.96"><div class="paperToolbar"><div class="paperExit"><button>Порвать листик и выкинуть</button></div><div class="rotateControls"><button>↶</button><button>Моя сторона</button><button>↷</button></div><button class="paperClose" aria-label="Закрыть пульку">×</button></div><span class="paperBody"><svg class="paper" viewBox="0 0 578 600"></svg></span></div>`);
  const close=page.getByRole("button",{name:"Закрыть пульку"});
  await expect(close).toHaveCSS("color","rgb(181, 21, 36)");
  const button=page.getByRole("button",{name:"Моя сторона"});
  const box=await button.boundingBox();
  expect(box!.height).toBeLessThanOrEqual(24);
  const line=await page.locator(".paperBody").evaluate(el=>getComputedStyle(el).backgroundImage);
  expect(line).toContain("repeating-linear-gradient");
  expect(read("Notebook.ru.tsx")).toContain('aria-label="Закрыть пульку"');
  expect(read("SharedRoom.ru.tsx")).toContain('p.overlay.kind==="radio"?styles.radioOverlay');
  expect(read("GameTable.ru.tsx")).toContain('view.score&&!view.presentation?.overlay');
});
