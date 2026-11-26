/** Bound outage traffic independently of presentation and financial timers. */
export function fallbackDelay(status: string | undefined, hidden: boolean, failures = 0): number {
  const base = failures > 0 ? Math.min(120_000, 15_000 * 2 ** Math.min(failures, 3))
    : status === "playing" ? 15_000 : status === "closed" || status === "archived" ? 60_000 : 30_000;
  return hidden ? Math.max(60_000, base) : base;
}

export class RequestCooldown {
  private until = 0;
  constructor(private readonly now: () => number = Date.now) {}
  remaining(): number { return Math.max(0, this.until - this.now()); }
  observe(status: number, retryAfter: string | null): void {
    if (![429, 502, 503, 504].includes(status)) return;
    const seconds = retryAfter && /^\d{1,4}$/.test(retryAfter) ? Number(retryAfter) : 0;
    const delay = Math.max(15_000, Math.min(600_000, seconds * 1000));
    // Do not reset the deadline when a local blocked request is rejected.
    if (!this.remaining()) this.until = this.now() + delay;
    else if (seconds > 0) this.until = Math.max(this.until, this.now() + delay);
  }
}

export const gameCooldown = new RequestCooldown();
