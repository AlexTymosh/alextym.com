/** Local protection for Firebase reads. Never caches admission, grants or user data. */
export const QUOTA_DETAIL = "Storage temporarily unavailable";
export class FirebaseQuotaUnavailable extends Error {
  constructor() { super(QUOTA_DETAIL); this.name = "FirebaseQuotaUnavailable"; }
}

export function isFirebaseQuota(error: unknown): boolean {
  const seen = new Set<unknown>();
  let current = error;
  while (current && typeof current === "object" && !seen.has(current)) {
    seen.add(current);
    if (current instanceof FirebaseQuotaUnavailable) return true;
    const value = current as { code?: unknown; name?: unknown; cause?: unknown };
    if (value.code === 8 || value.code === "8" || value.code === "RESOURCE_EXHAUSTED" ||
        value.code === "resource-exhausted" || value.code === "firestore/resource-exhausted" ||
        value.name === "ResourceExhausted") return true;
    current = value.cause;
  }
  return false;
}

export class FirebaseQuotaCircuit {
  private until = 0;
  private last = -Infinity;
  private streak = 0;
  constructor(private readonly now: () => number = Date.now) {}
  remaining(): number { return Math.max(0, Math.ceil((this.until - this.now()) / 1000)); }
  requireAvailable(): void { if (this.remaining()) throw new FirebaseQuotaUnavailable(); }
  observe(error: unknown): boolean {
    if (!isFirebaseQuota(error)) return false;
    if (!(error instanceof FirebaseQuotaUnavailable)) this.open();
    return true;
  }
  open(seconds?: number): void {
    const at = this.now();
    if (at < this.until) return;
    if (at - this.last >= 1_800_000) this.streak = 0;
    this.streak = Math.min(4, this.streak + 1);
    this.last = at;
    const delay = seconds === undefined || !Number.isFinite(seconds)
      ? Math.min(600, 120 * 2 ** (this.streak - 1)) : Math.min(600, Math.max(1, seconds));
    this.until = at + delay * 1000;
  }
  async run<T>(operation: () => Promise<T>): Promise<T> {
    this.requireAvailable();
    try { return await operation(); }
    catch (error) { this.observe(error); throw error; }
  }
}

export const firebaseQuota = new FirebaseQuotaCircuit();
