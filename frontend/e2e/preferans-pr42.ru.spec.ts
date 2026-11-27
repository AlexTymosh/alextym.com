import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root=resolve(process.cwd(),"../portfolio/preferans/frontend/src");
const read=(file:string)=>readFileSync(resolve(root,file),"utf8");
const css=["preferans-game.module.css","preferans-table.module.css"].map(read).join("\n");

// These fixtures exercise real styles and the production parent/child relationship.
test("auction labels are anchored to avatars rather than wide seat grid cells",async({page})=>{
  expect(read("GameTable.ru.tsx")).toContain('<div className={styles.avatarAnchor}>{speech&&<span className={styles.callBubble}>');
  await page.setViewportSize({width:1664,height:912});
  await page.setContent(`<style>${css}\n*{box-sizing:border-box}body{margin:0}</style><main class="root tableRoot"><div class="tableScene" style="--table-zoom:1"><section class="table" data-playing="true" style="--available-table-height:812px"><div class="tableTop">${["left","center","right"].map(pos=>pos==="center"?'<div class="center"><div class="trickField"></div></div>':`<section class="seat ${pos}"><div class="avatarAnchor"><span class="callBubble">Пас</span><div class="identity"><div class="avatar"></div></div></div></section>`).join("")}</div></section></div></main>`);
  for(const zoom of [.7,1,1.3]){
    await page.locator(".tableScene").evaluate((el,value)=>(el as HTMLElement).style.setProperty("--table-zoom",String(value)),zoom);
    const boxes=await page.locator(".avatarAnchor").evaluateAll(nodes=>nodes.map(el=>{
      const a=el.querySelector(".avatar")!.getBoundingClientRect(), b=el.querySelector(".callBubble")!.getBoundingClientRect();
      return {left:b.left-a.left,top:b.top-a.top,right:a.right-b.right};
    }));
    for(const box of boxes){expect(box.left).toBeGreaterThanOrEqual(0);expect(box.left).toBeLessThanOrEqual(16);expect(box.top).toBeGreaterThanOrEqual(0);expect(box.right).toBeGreaterThanOrEqual(-1);}
  }
  await page.locator(".table").evaluate(el=>(el as HTMLElement).dataset.gagFake="true");
  await expect(page.locator(".callBubble").first()).toBeHidden();
});

for(const [width,height] of [[1664,912],[1272,624]]){
  test(`contract declaration does not narrow the unchanged hand at ${width}x${height}`,async({page})=>{
    expect(read("PreferansGame.ru.tsx")).not.toContain("data-discard-inline");
    await page.setViewportSize({width,height});
    const cards=Array.from({length:10},(_,i)=>`<div class="cardWithSort" data-hand-card="true" ${[3,6,8].includes(i)?'data-suit-break="true"':''}><button type="button" class="playingCard" data-card="${i}"></button></div>`).join("");
    await page.setContent(`<style>${css}\n*{box-sizing:border-box}body{margin:0}</style><main class="root tableRoot"><div class="tableScene" style="--table-zoom:1;width:${width-24}px"><section class="table" data-playing="true" data-furniture="true" style="--available-table-height:${height-100}px"><div class="tableTop"><div></div><div class="center"><div class="trickField"></div></div><div></div></div><div class="bottomArea" style="--hand-count:10;--hand-breaks:3"><div class="seat bottom"><div class="avatar"></div></div><div class="handColumn"><div class="ownHand" data-own-hand="true"><div class="handsPanel"><div class="declareRow" data-declaration="true"><div class="declareBids"><section class="actionPanel"><button>7</button><button>8</button><button>Мизер</button></section></div><div class="discardReview"><div class="discardSlots"><span class="discardSlot"></span><span class="discardSlot"></span><button>◉</button></div></div></div><div class="handRow">${cards}</div></div></div></div><div class="bottomFurniture">Radio</div></div></section></div></main>`);
    const measure=()=>page.evaluate(()=>{
      const row=document.querySelector(".handRow")!.getBoundingClientRect(), card=document.querySelector("[data-card]")!.getBoundingClientRect(), table=document.querySelector(".table")!.getBoundingClientRect(), review=document.querySelector(".declareRow")!.getBoundingClientRect();
      return {rowWidth:row.width, cardHeight:card.height, gap:card.top-review.bottom, bottom:table.bottom-card.bottom};
    });
    for(const zoom of [.7,1,1.3]){
      await page.locator(".tableScene").evaluate((el,value)=>(el as HTMLElement).style.setProperty("--table-zoom",String(value)),zoom);
      await page.locator(".declareBids").evaluate(el=>(el as HTMLElement).style.display="");
      const before=await measure();
      await page.locator(".declareBids").evaluate(el=>(el as HTMLElement).style.display="none");
      const after=await measure();
      expect(after.rowWidth).toBeCloseTo(before.rowWidth,0);
      // Freeing the declaration buttons may increase capacity on a short viewport, never reduce it.
      expect(after.cardHeight).toBeGreaterThanOrEqual(before.cardHeight-1);
      expect(after.cardHeight).toBeGreaterThan(12);
      expect(after.gap).toBeGreaterThanOrEqual(-1);expect(after.gap).toBeLessThanOrEqual(14);
      expect(after.bottom).toBeGreaterThanOrEqual(3);
    }
  });
}
