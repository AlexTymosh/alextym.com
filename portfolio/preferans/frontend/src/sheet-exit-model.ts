export function isSeat(value: unknown): value is number {
  return typeof value === "number" && [0, 1, 2].includes(value);
}
