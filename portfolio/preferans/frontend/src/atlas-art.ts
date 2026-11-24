import type { Card, Suit } from "./game-model.ru";
import { isCard } from "./table-model";

// Original vector artwork, drawn for this module. No scanned deck or remote image.
const pips: Record<Suit, string> = {
  S: "M0 -11 C-3 -6 -12 -2 -12 4 C-12 12 -3 12 0 6 C3 12 12 12 12 4 C12 -2 3 -6 0 -11 Z M-1 5 L-5 12 H5 L1 5 Z",
  H: "M0 11 C-5 6 -12 1 -12 -5 C-12 -12 -4 -14 0 -7 C4 -14 12 -12 12 -5 C12 1 5 6 0 11Z",
  D: "M0 -13 L10 0 L0 13 L-10 0 Z",
  C: "M0 -12 A6 6 0 1 1 -4 -1 A6 6 0 1 1 -2 7 L-5 12 H5 L2 7 A6 6 0 1 1 4 -1 A6 6 0 1 1 0 -12Z",
};
const ranks: Record<number, string> = { 7:"7",8:"8",9:"9",10:"10",11:"\u0412",12:"\u0414",13:"\u041a",14:"\u0422" };
const ink = (suit: Suit) => suit === "H" || suit === "D" ? "#a32935" : "#17242a";
const pip = (suit: Suit, x: number, y: number, size = 1, rotate = 0) => `<path d="${pips[suit]}" transform="translate(${x} ${y}) rotate(${rotate}) scale(${size})" fill="${ink(suit)}"/>`;
const wrap = (body: string) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 146" width="100" height="146"><rect x=".5" y=".5" width="99" height="145" rx="6" fill="#fff9eb" stroke="#b8a589"/>${body}</svg>`;
const uri = (svg: string) => `data:image/svg+xml,${encodeURIComponent(svg)}`;

function court(rank: number, suit: Suit): string {
  const red = ink(suit), blue = "#34566a", gold = "#b99146", outline = "#26343c";
  const crown = rank === 13 ? `<path d="M29 24L27 9 37 15 43 5 50 15 57 5 63 15 73 9 71 24Z" fill="${gold}"/>`
    : rank === 12 ? `<path d="M28 24L33 13 42 16 50 5 58 16 67 13 72 24Z" fill="${gold}"/><circle cx="50" cy="8" r="3" fill="#a32935"/>`
    : `<path d="M28 24Q37 6 58 10L75 19 62 25Z" fill="${blue}"/><path d="M58 12L76 4 69 18" fill="${gold}"/>`;
  const emblem = rank === 13 ? `<path d="M76 24L79 62M70 32H84" stroke="${gold}" stroke-width="3"/>`
    : rank === 12 ? `<path d="M76 24V63M70 37Q78 30 83 38" stroke="${gold}" stroke-width="2"/><circle cx="76" cy="23" r="5" fill="#a32935"/>`
    : `<path d="M77 27L75 63M72 31L77 22 82 31Z" stroke="${gold}" fill="${gold}"/>`;
  const half = `<g stroke="${outline}" stroke-width="1.1" stroke-linejoin="round"><path d="M20 72L25 54Q33 44 50 46Q67 44 75 54L82 72Z" fill="${blue}"/><path d="M31 51L46 72H54L69 51 59 46 50 56 41 46Z" fill="${red}"/><path d="M26 59L37 64 29 72M74 59L63 64 71 72M42 72L50 60 58 72" fill="none" stroke="${gold}" stroke-width="3"/><path d="M31 25Q30 13 50 13Q70 13 69 25L68 45 60 51 40 51 32 45Z" fill="#a17a45"/><path d="M37 24Q50 18 63 24L62 39Q60 49 50 50Q40 49 38 39Z" fill="#f2d5a9"/><path d="M42 31H46M54 31H58M50 32L48 38H51M46 42Q50 44 54 42" fill="none" stroke-width="1.5"/>${rank === 13 ? `<path d="M41 40Q50 36 59 40L56 48 50 53 44 48Z" fill="#684a38"/><path d="M46 41H54" stroke="#f2d5a9"/>` : ""}${crown}${emblem}<path d="M22 69L29 56M78 69L71 56" stroke="${gold}" stroke-width="2"/></g>`;
  return `<rect x="17" y="20" width="66" height="106" fill="#e8dab9" stroke="#b99146" stroke-width="1.2"/><g transform="translate(0 10)">${half}</g><g transform="rotate(180 50 73) translate(0 10)">${half}</g><path d="M19 73H81" stroke="${gold}" stroke-width="1.5"/>`;
}
export function faceSvg(card: Card): string {
  if (!isCard(card)) throw new Error("Invalid card artwork request");
  const {rank,suit} = card;
  const corner = `<g fill="${ink(suit)}" font-family="Georgia,serif" font-weight="bold"><text x="10" y="17" text-anchor="middle" font-size="${rank===10?13:17}">${ranks[rank]}</text>${pip(suit,10,29,.47)}</g>`;
  let center = "";
  if (rank >= 11 && rank <= 13) center = court(rank,suit);
  else if (rank === 14) center = pip(suit,50,73,2.25);
  else {
    const ys = rank >= 9 ? [27,57,89,119] : [28,73,118];
    center = ys.map(y => pip(suit,30,y,.79,y>73?180:0)+pip(suit,70,y,.79,y>73?180:0)).join("");
    const extras = rank===7 ? [48] : rank===8 ? [48,98] : rank===9 ? [73] : [42,104];
    center += extras.map(y=>pip(suit,50,y,.75,y>73?180:0)).join("");
  }
  return wrap(`${center}${corner}<g transform="rotate(180 50 73)">${corner}</g>`);
}
export function backSvg(): string {
  return wrap(`<defs><pattern id="weave" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="9" height="9" fill="#9c3e49"/><path d="M0 0V9M4.5 0V9M0 0H9M0 4.5H9" stroke="#f2d4c1" stroke-width=".55"/><circle cx="2.25" cy="2.25" r=".7" fill="#f3debd"/></pattern></defs><rect x="6" y="6" width="88" height="134" rx="4" fill="#963944" stroke="#7c2935"/><rect x="10" y="10" width="80" height="126" rx="2" fill="url(#weave)" stroke="#f2d4c1" stroke-width="1.5"/><rect x="13" y="13" width="74" height="120" rx="2" fill="none" stroke="#f2d4c1" stroke-width=".7"/><path d="M50 52L65 73 50 94 35 73Z" fill="#f2d4c1" stroke="#7c2935"/><path d="M50 57L60 73 50 89 40 73Z" fill="#963944"/>`);
}
const cache = new Map<string,string>();
export function cardArtwork(card: Card): string {
  if (!isCard(card)) throw new Error("Invalid card artwork request");
  const key = `${card.suit}${card.rank}`;
  const existing = cache.get(key);
  if (existing) return existing;
  const result = uri(faceSvg(card)); cache.set(key,result); return result;
}
export const cardBackArtwork = uri(backSvg());
