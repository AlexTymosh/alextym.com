/**
 * Workforce uses its own password gate. Vercel supplies the routed Host, while
 * the browser supplies Origin; compare them without Portfolio Lab configuration.
 */
export function hasWorkforceOrigin(request: Request, onVercel = Boolean(process.env.VERCEL)): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const source = new URL(origin);
    const target = new URL(request.url);
    const targetHost = request.headers.get("host") ?? (onVercel ? null : target.host);
    if (source.origin !== origin || source.host !== targetHost) return false;
    return source.protocol === (onVercel ? "https:" : target.protocol);
  } catch {
    return false;
  }
}
