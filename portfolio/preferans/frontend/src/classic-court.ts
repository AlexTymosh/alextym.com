import type { Suit } from "./game-model.ru";

// Original two-ended line art, using the palette and silhouette conventions
// of traditional Eastern European atlas decks, not a scan of a commercial deck.
export function classicCourt(rank: number, suit: Suit): string {
  const colour = {S:"#243b91",C:"#225e49",D:"#bd2729",H:"#2358a3"}[suit];
  const trim = {S:"#cb3032",C:"#c4312c",D:"#24478e",H:"#c6272b"}[suit];
  const gold = "#e2b328", black = "#231f20", skin = "#df9b53";
  const crown = rank===13 ? `<path d="M32 19L29 6 38 12 43 4 50 12 57 4 63 12 71 6 68 19Z" fill="${gold}"/><path d="M31 17Q50 12 69 17M34 10l4 4m6-4 4 4m8-4 4 4m5-4 3 4" fill="none"/>`
    : rank===12 ? `<path d="M31 20Q35 3 51 6Q67 4 70 20L75 51 62 45 57 21 40 19 37 48 26 51Z" fill="${colour}"/><path d="M33 15Q50 4 67 15M31 18Q50 8 69 18" fill="none" stroke="${gold}" stroke-width="2"/><path d="M38 11L43 4 50 9 57 4 62 11" fill="${gold}"/>`
    : `<path d="M29 19Q30 2 53 6L70 15 63 22 44 16Z" fill="${trim}"/><path d="M50 10L72 0 64 15Z" fill="${gold}"/><path d="M29 18Q44 12 65 21" stroke="${gold}" stroke-width="3" fill="none"/>`;
  const hair = rank===12 ? `<path d="M35 18Q26 29 30 49L36 55 42 46 39 23M60 18Q72 29 66 51L58 53 59 33" fill="#714020"/><path d="M34 23Q30 38 35 47M64 24Q70 39 63 49" fill="none"/>`
    : `<path d="M35 19Q26 29 31 43L37 46 41 35M64 18Q73 28 68 44L61 47 57 34" fill="#9c6637"/><path d="M34 24L32 36M65 23L68 36" fill="none"/>`;
  const beard = rank===13 ? `<path d="M38 35Q42 38 50 37Q58 38 63 34L62 49 56 55 51 52 46 56 40 48Z" fill="#ded3b3"/><path d="M42 43L45 49M49 43L50 51M55 43L56 49M43 39Q47 35 50 39Q53 35 57 39" fill="none"/>` : rank===11 ? `<path d="M44 37Q48 34 51 37Q55 34 59 37" fill="none" stroke-width="1.5"/>` : `<path d="M45 40Q51 42 55 39" fill="none" stroke="#a92228" stroke-width="1.7"/>`;
  const item = rank===12 ? `<path d="M75 23L72 60M75 31L82 26M74 38L67 33" stroke="#236341" stroke-width="2" fill="none"/><path d="M74 18L78 12 82 18 87 21 82 25 77 30 74 25 69 21Z" fill="${trim}"/><circle cx="78" cy="21" r="2" fill="${gold}"/>` : `<path d="M77 9L80 45 76 52 73 45Z" fill="#d5d6cd"/><path d="M76 12L77 43M69 48H83M77 49V67" stroke="${gold}" stroke-width="2.5"/>`;
  const side = `<g stroke="${black}" stroke-width=".8" stroke-linejoin="round" stroke-linecap="round">
    <path d="M17 73L22 55 33 46 44 44 57 44 68 46 79 55 83 73Z" fill="${colour}"/>
    <path d="M25 53L38 48 50 67 62 48 75 53 68 73H32Z" fill="${trim}"/>
    <path d="M36 50L50 73 64 50M25 57L36 62 30 70M75 57L64 62 70 70" stroke="${gold}" stroke-width="2.7" fill="none"/>
    <path d="M40 49L50 55 60 49 57 44H43Z" fill="${skin}"/>
    <path d="M39 18Q50 13 62 19L63 31 60 42 51 48 42 43 38 33Z" fill="${skin}"/>
    ${hair}<path d="M42 26Q45 24 48 26M53 26Q57 24 60 26M43 28H47M54 28H58M51 28L48 34 52 35" fill="none"/>
    <path d="M42 29h2m12 0h2" stroke-width="1.5"/>${beard}${crown}
    <path d="M20 73L24 61 31 65 26 73M80 73L76 61 69 65 74 73" fill="${gold}"/>
    ${[0,1,2,3].map(i=>`<path d="M${38+i*7} 63l3 3-3 3-3-3Z" fill="${gold}"/>`).join("")}
    ${item}<path d="M69 55Q75 50 80 54L81 60 76 63 72 61Z" fill="${skin}"/><path d="M73 56l6 1m-6 2 6 1" fill="none"/>
  </g>`;
  return `<rect x="17" y="20" width="66" height="106" fill="#f5f1e5" stroke="${black}" stroke-width=".7"/><g transform="translate(0 12) scale(1 .84)">${side}</g><g transform="rotate(180 50 73) translate(0 12) scale(1 .84)">${side}</g><path d="M17 73H83" stroke="${black}" stroke-width=".7"/>`;
}
