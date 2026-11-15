import "server-only";

export const WORKFORCE_COOKIE = "workforce_demo_session";
export const WORKFORCE_COOKIE_PATH = "/portfolio/workforce-intelligence";
export const WORKFORCE_SESSION_TTL = 8 * 3600;

export function workforceEnabled() {
  return process.env.WORKFORCE_INTELLIGENCE_ENABLED === "true";
}

export function workforceBackendOrigin() {
  const raw = process.env.BACKEND_ORIGIN?.trim();
  if (!raw) throw new Error("Backend origin missing");
  const url = new URL(raw);
  if (!["https:", "http:"].includes(url.protocol) ||
      (process.env.NODE_ENV === "production" && url.protocol !== "https:") ||
      url.pathname !== "/" || url.username || url.password || url.search || url.hash) {
    throw new Error("Invalid backend origin");
  }
  return url.origin;
}
