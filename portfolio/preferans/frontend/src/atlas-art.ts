import type { Card, Suit } from "./game-model.ru";
import { isCard } from "./table-model";
import { classicCourt } from "./classic-court";
import type { BackTheme } from "./table-interaction";

// Original vector artwork, drawn for this module. No scanned deck or remote image.
const pips: Record<Suit, string> = {
  S: "M0 -11 C-3 -6 -12 -2 -12 4 C-12 12 -3 12 0 6 C3 12 12 12 12 4 C12 -2 3 -6 0 -11 Z M-1 5 L-5 12 H5 L1 5 Z",
  H: "M0 11 C-5 6 -12 1 -12 -5 C-12 -12 -4 -14 0 -7 C4 -14 12 -12 12 -5 C12 1 5 6 0 11Z",
  D: "M0 -13 L10 0 L0 13 L-10 0 Z",
  C: "M0 -12 A6 6 0 1 1 -4 -1 A6 6 0 1 1 -2 7 L-5 12 H5 L2 7 A6 6 0 1 1 4 -1 A6 6 0 1 1 0 -12Z",
};
const ranks: Record<number, string> = { 7:"7",8:"8",9:"9",10:"10",11:"\u0412",12:"\u0414",13:"\u041a",14:"\u0422" };
const ink = (suit: Suit) => suit === "H" || suit === "D" ? "#c9181e" : "#171717";
const pip = (suit: Suit, x: number, y: number, size = 1, rotate = 0) => `<path d="${pips[suit]}" transform="translate(${x} ${y}) rotate(${rotate}) scale(${size})" fill="${ink(suit)}"/>`;
const wrap = (body: string) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 146" width="100" height="146"><rect x=".5" y=".5" width="99" height="145" rx="6" fill="#fff9eb" stroke="#b8a589"/>${body}</svg>`;
const uri = (svg: string) => `data:image/svg+xml,${encodeURIComponent(svg)}`;

export function faceSvg(card: Card): string {
  if (!isCard(card)) throw new Error("Invalid card artwork request");
  const {rank,suit} = card;
  const corner = `<g fill="${ink(suit)}" font-family="Arial Narrow,Arial,sans-serif" font-weight="bold"><text x="10" y="17" text-anchor="middle" font-size="${rank===10?13:17}">${ranks[rank]}</text>${pip(suit,10,29,.47)}</g>`;
  let center = "";
  if (rank >= 11 && rank <= 13) center = classicCourt(rank,suit);
  else if (rank === 14) center = pip(suit,50,73,2.25);
  else {
    const ys = rank >= 9 ? [27,57,89,119] : [28,73,118];
    center = ys.map(y => pip(suit,30,y,.79,y>73?180:0)+pip(suit,70,y,.79,y>73?180:0)).join("");
    const extras = rank===7 ? [48] : rank===8 ? [48,98] : rank===9 ? [73] : [42,104];
    center += extras.map(y=>pip(suit,50,y,.75,y>73?180:0)).join("");
  }
  return wrap(`${center}${corner}<g transform="rotate(180 50 73)">${corner}</g>`).replace('fill="#fff9eb"','fill="#f8f7f1"');
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

// Original symmetric patterns inspired by the Owner-provided references.
export function themedBackSvg(theme: BackTheme): string {
  if (theme === "classic") return backSvg();
  if (theme === "ornament") return wrap(`<defs><pattern id="rosette" width="12" height="12" patternUnits="userSpaceOnUse"><rect width="12" height="12" fill="#c81928"/><path d="M6 0Q10 3 6 6Q2 3 6 0M0 6Q3 2 6 6Q3 10 0 6M6 6Q10 9 6 12Q2 9 6 6M6 6Q9 2 12 6Q9 10 6 6" fill="#fff8eb"/></pattern></defs><rect x="5" y="5" width="90" height="136" rx="4" fill="#c81928"/><rect x="9" y="9" width="82" height="128" fill="none" stroke="#fff8eb" stroke-width="2"/><rect x="15" y="15" width="70" height="116" fill="url(#rosette)" stroke="#fff8eb" stroke-width="2"/><rect x="25" y="25" width="50" height="96" fill="none" stroke="#fff8eb" stroke-width="4"/><rect x="29" y="29" width="42" height="88" fill="url(#rosette)" stroke="#fff8eb"/>`);
  const a=theme==="green"?"#165b45":"#c54d54", b=theme==="green"?"#722f31":"#48a2c4";
  const lines=Array.from({length:5},(_,i)=>`M${i*2.5} 0V44 M0 ${i*2.5+22}H44`).join(" ");
  const cross=Array.from({length:5},(_,i)=>`M${i*2.5+22} 0V44 M0 ${i*2.5}H44`).join(" ");
  return wrap(`<defs><pattern id="plaid" width="44" height="44" patternUnits="userSpaceOnUse" patternTransform="rotate(45 50 73)"><rect width="44" height="44" fill="#f5f3ec"/><path d="${lines}" stroke="${a}" fill="none" stroke-width="1.15"/><path d="${cross}" stroke="${b}" fill="none" stroke-width=".85"/></pattern></defs><rect x="3" y="3" width="94" height="140" rx="5" fill="url(#plaid)"/>`);
}
const backCache = new Map<BackTheme,string>();
export function themedBackArtwork(theme: BackTheme): string {
  if (theme === "classic") return cardBackArtwork;
  const found=backCache.get(theme); if(found) return found;
  const value=uri(themedBackSvg(theme)); backCache.set(theme,value); return value;
}
