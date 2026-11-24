export type SeatSwap = { id: number; from: number; to: number; votes: boolean[] };

function seat(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 2;
}

export function isSeatSwap(value: unknown): value is SeatSwap {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  return Object.keys(v).length === 4 && typeof v.id === "number" && Number.isSafeInteger(v.id) && v.id > 0 &&
    seat(v.from) && seat(v.to) && v.from !== v.to && Array.isArray(v.votes) && v.votes.length === 3 &&
    v.votes.every(x => typeof x === "boolean") && v.votes[v.from] === true && !v.votes.every(Boolean);
}
