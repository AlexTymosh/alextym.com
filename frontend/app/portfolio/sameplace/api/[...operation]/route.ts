import { NextRequest, NextResponse } from "next/server";
import { roomOperation } from "@sameplace";
import { getLabAdminAuth, isLabEnabled, LAB_SESSION_COOKIE, LAB_SESSION_MAX_AGE_MS } from "../../../../../lib/portfolio-lab/firebase-server";
import { hasSameOrigin } from "../../../../../lib/portfolio-lab/session-origin";
import { hasLabJsonContent, readLabJson } from "../../../../../lib/portfolio-lab/request-json";
import { isRecentLabLogin } from "../../../../../lib/portfolio-lab/session-policy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const cookieName = process.env.NODE_ENV === "production" ? "__Secure-sameplace_session" : "sameplace_session";
const cookieOptions = { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "strict" as const, path: "/portfolio/sameplace", maxAge: LAB_SESSION_MAX_AGE_MS / 1000 };
function reply(status: number, data: object, retry?: string | null) {
  const headers = new Headers({ "Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff" });
  if (retry && /^\d{1,5}$/.test(retry)) headers.set("Retry-After", retry);
  return NextResponse.json(data, { status, headers });
}
function backend(path: string) {
  const configured = process.env.BACKEND_ORIGIN?.trim();
  if (!configured) throw new Error("Backend unavailable");
  const base = new URL(configured);
  if (base.username || base.password || base.search || base.hash || base.pathname !== "/" ||
    (base.protocol !== "https:" && !(base.protocol === "http:" && !process.env.VERCEL && ["localhost","127.0.0.1"].includes(base.hostname)))) throw new Error("Invalid backend origin");
  return new URL(`/api/sameplace/${path}`, base);
}
async function forward(path: string, method: string, authorization: string, body?: object) {
  try {
    const response = await fetch(backend(path), { method, headers: { Authorization: authorization, Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}), cache: "no-store", redirect: "error", signal: AbortSignal.timeout(25000) });
    const data: unknown = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data) || (!response.ok && ![400,401,403,404,405,409,413,415,422,429,503].includes(response.status))) return reply(502, {detail:"UNAVAILABLE"});
    return reply(response.status, data, response.headers.get("Retry-After"));
  } catch { return reply(502, {detail:"UNAVAILABLE"}); }
}
type Context = { params: Promise<{ operation: string[] }> };
async function handle(request: NextRequest, context: Context) {
  if (!isLabEnabled() || process.env.SAMEPLACE_ENABLED !== "true") return reply(404, {detail:"Not found"});
  const { operation } = await context.params;
  const session = request.method === "POST" && operation.length === 1 && operation[0] === "session";
  const logout = request.method === "POST" && operation.length === 1 && operation[0] === "signout";
  const path = roomOperation(request.method, operation);
  if (!path && !session && !logout) return reply(404, {detail:"Not found"});
  if (request.nextUrl.search) return reply(400, {detail:"INVALID_REQUEST"});
  let payload: Record<string, unknown> | undefined;
  if (request.method === "POST") {
    if (!hasSameOrigin(request)) return reply(403, {detail:"ACCESS_DENIED"});
    if (!hasLabJsonContent(request)) return reply(415, {detail:"INVALID_CONTENT_TYPE"});
    const body = await readLabJson(request, 16384);
    if (body === "too_large") return reply(413, {detail:"REQUEST_TOO_LARGE"});
    if (!body) return reply(422, {detail:"INVALID_REQUEST"});
    payload = body;
  }
  if (logout) {
    const response = reply(200, {ok:true});
    // Explicit local logout suppresses fallback to the separate site session.
    response.cookies.set(cookieName, "signed-out", cookieOptions);
    return response;
  }
  if (session) {
    const idToken = payload?.idToken;
    if (typeof idToken !== "string" || !idToken || idToken.length > 8192) return reply(401, {detail:"AUTH_REQUIRED"});
    try {
      const admin = await getLabAdminAuth();
      const claims = await admin.verifyIdToken(idToken, true);
      if (!isRecentLabLogin(claims.auth_time)) return reply(403, {detail:"ACCESS_DENIED"});
      // Backend verifies identity and existing Lab denial policy before session creation.
      const access = await forward("identity", "GET", `Bearer ${idToken}`);
      if (!access.ok) return access;
      const cookie = await admin.createSessionCookie(idToken, {expiresIn: LAB_SESSION_MAX_AGE_MS});
      const response = reply(200, {ok:true});
      response.cookies.set(cookieName, cookie, cookieOptions);
      return response;
    } catch { return reply(401, {detail:"AUTH_REQUIRED"}); }
  }
  const credential = request.cookies.get(cookieName)?.value ?? request.cookies.get(LAB_SESSION_COOKIE)?.value;
  if (!credential || credential === "signed-out" || credential.length > 8192) return reply(401, {detail:"AUTH_REQUIRED"});
  return forward(path!, request.method, `FirebaseSession ${credential}`, payload);
}
export const GET = handle;
export const POST = handle;
