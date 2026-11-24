export type SheetOffer = { id: number; from: number; to: number };
export function isSeat(value: unknown): value is number {
  return typeof value === "number" && [0, 1, 2].includes(value);
}
export function isSheetOffers(value: unknown): value is SheetOffer[] {
  if (!Array.isArray(value) || value.length > 3) return false;
  const ids = new Set<number>();
  const targets = new Set<number>();
  for (const offer of value) {
    if (!offer || typeof offer !== "object" || Array.isArray(offer) ||
        Object.keys(offer).length !== 3 || !Number.isSafeInteger(offer.id) || offer.id < 1 ||
        !isSeat(offer.from) || !isSeat(offer.to) || offer.from === offer.to ||
        ids.has(offer.id) || targets.has(offer.to)) return false;
    ids.add(offer.id); targets.add(offer.to);
  }
  return true;
}
