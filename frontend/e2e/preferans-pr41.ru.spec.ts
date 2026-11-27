import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(process.cwd(), "../portfolio/preferans/frontend/src");
const css = ["preferans-game.module.css", "preferans-table.module.css"]
  .map(file => readFileSync(resolve(root, file), "utf8")).join("\n");

for (const [width, height] of [[1664, 912], [1272, 624], [800, 450]]) {
  test(`compact hand controls at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    for (const phase of ["auction", "discard", "declare", "claim", "raised", "review"]) {
      const cards = Array.from({length:12}, (_,i) => `<div class="cardWithSort" data-hand-card="true" ${[3,6,9].includes(i)?'data-suit-break="true"':''}><button type="button" class="playingCard" data-card="${i}" ${phase==="raised"&&i===2?'data-defense-raised="true"':''} style="background:white"></button></div>`).join("");
      const review = `<div class="discardReview"><div class="discardSlots"><span class="discardSlot"></span><span class="discardSlot"></span><button>◉</button></div></div>`;
      const inner = phase==="discard" ? `<div class="discardSlots" data-controls><span class="discardSlot"></span><span class="discardSlot"></span><div class="discardActions"><button>◉</button><button>Снести две карты</button><button>Спрятать надежно</button></div></div>` : phase==="declare" ? `<div class="declareRow" data-controls><div class="declareBids"><section class="actionPanel"><button>6</button><button>7</button><button>8</button></section></div>${review}</div>` : phase==="review" ? `<div class="declareRow" data-controls>${review}</div>` : "";
      const controls = phase==="auction" ? `<div class="decision" data-controls><section class="actionPanel"><button>Пас</button><button>6</button><button>7</button></section></div>` : ["claim","raised"].includes(phase) ? `<div class="claimButton" data-controls><button>Все мои</button><button>По своим</button></div>` : "";
      await page.setContent(`<meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}\n*{box-sizing:border-box}body{margin:0}</style><main class="root tableRoot"><div class="tableScene" style="--table-zoom:1;width:${width-24}px"><section class="table" data-playing="true" data-furniture="true" style="--available-table-height:${height-100}px"><div class="tableTop"><div class="seat"><div class="avatar"></div></div><div class="center"><div class="trickField"></div></div><div class="seat"><div class="avatar"></div></div></div><div class="bottomArea" style="--hand-count:12;--hand-breaks:3"><div class="seat bottom"><div class="avatar"></div></div><div class="handColumn"><span class="firstHand">Ход за тобой</span>${controls}<div class="ownHand" data-own-hand="true"><div class="handsPanel">${inner}<div class="handRow">${cards}</div></div></div></div><div class="bottomFurniture">Radio</div></div></section></div></main>`);
      const table = page.locator(".table"), field = page.locator(".trickField");
      const initialTable = (await table.boundingBox())!, initialField = (await field.boundingBox())!;
      for (const scale of [.7,1,1.3]) {
        await page.locator(".tableScene").evaluate((el, zoom) => (el as HTMLElement).style.setProperty("--table-zoom", String(zoom)), scale);
        const geometry = await page.evaluate(() => {
          const t = document.querySelector(".table")!.getBoundingClientRect();
          const c = document.querySelector("[data-controls]")!.getBoundingClientRect();
          const cards = Array.from(document.querySelectorAll("[data-card]")).map(el => el.getBoundingClientRect());
          const top = Math.min(...cards.map(r=>r.top));
          return { gap: top-c.bottom, inside: cards.every(r=>r.width>8&&r.top>=t.top&&r.bottom<=t.bottom-3&&r.left>=t.left&&r.right<=t.right) };
        });
        const label = `${phase}, ${width}x${height}, scale ${scale}`;
        expect(geometry.inside,label).toBe(true);
        // The discard review now stays immediately above the hand as well.
        expect(geometry.gap,label).toBeGreaterThanOrEqual(-1);
        expect(geometry.gap,label).toBeLessThanOrEqual(14);
        expect((await table.boundingBox())!.height,label).toBeCloseTo(initialTable.height,0);
        expect((await field.boundingBox())!.width,label).toBeCloseTo(initialField.width,0);
      }
    }
  });
}
