/** Cross-site requests cannot create or destroy browser sessions. */
export function hasSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const configured = process.env.PORTFOLIO_LAB_ORIGIN?.trim();
    if (process.env.VERCEL && !configured) return false;
    if (!configured) return origin === new URL(request.url).origin;
    const trusted = new URL(configured);
    // Vercel supplies Host for the requested alias. Restrict mutations to
    // that alias so alternate deployment URLs cannot evade its WAF rule.
    if (process.env.VERCEL && request.headers.get("host") !== trusted.host) return false;
    return configured === trusted.origin && origin === trusted.origin &&
      (trusted.protocol === "https:" ||
        (!process.env.VERCEL && trusted.protocol === "http:" &&
          (trusted.hostname === "127.0.0.1" || trusted.hostname === "localhost")));
  } catch {
    return false;
  }
}
