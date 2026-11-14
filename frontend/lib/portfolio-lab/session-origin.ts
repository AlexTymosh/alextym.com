/** Cross-site requests cannot create or destroy browser sessions. */
export function hasSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const configured = process.env.PORTFOLIO_LAB_ORIGIN?.trim();
    if (process.env.VERCEL && !configured) return false;
    if (!configured) return origin === new URL(request.url).origin;
    const trusted = new URL(configured);
    return configured === trusted.origin && origin === trusted.origin &&
      (trusted.protocol === "https:" ||
        (!process.env.VERCEL && trusted.protocol === "http:" &&
          (trusted.hostname === "127.0.0.1" || trusted.hostname === "localhost")));
  } catch {
    return false;
  }
}
