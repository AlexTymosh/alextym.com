import { NextRequest, NextResponse } from "next/server";
import {
  getLabAdminAuth,
  getOwnerUid,
  isLabEnabled,
  LAB_SESSION_COOKIE,
  LAB_SESSION_MAX_AGE_MS,
} from "../../../lib/portfolio-lab/firebase-server";
import { hasSameOrigin } from "../../../lib/portfolio-lab/session-origin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const json = (data: object, status: number) =>
  NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });

const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "strict" as const,
  path: "/",
  maxAge: LAB_SESSION_MAX_AGE_MS / 1000,
};

export async function POST(request: NextRequest) {
  if (!isLabEnabled()) return json({ error: "Not found" }, 404);
  if (!hasSameOrigin(request) || !request.headers.get("content-type")?.startsWith("application/json")) {
    return json({ error: "Invalid request origin or content type" }, 403);
  }
  const ownerUid = getOwnerUid();
  if (!ownerUid) return json({ error: "Lab unavailable" }, 503);
  const body = await request.json().catch(() => null);
  const idToken = body && typeof body.idToken === "string" ? body.idToken : "";
  if (!idToken || idToken.length > 8192) return json({ error: "Invalid token" }, 400);
  try {
    const admin = getLabAdminAuth();
    const decoded = await admin.verifyIdToken(idToken, true);
    const now = Date.now() / 1000;
    if (decoded.uid !== ownerUid || typeof decoded.auth_time !== "number" || now - decoded.auth_time > 300 || decoded.auth_time > now + 60) {
      return json({ error: "Identity not permitted or recent login required" }, 403);
    }
    // PR 3 replaces the temporary Owner-only admission with durable grant checks.
    const cookie = await admin.createSessionCookie(idToken, { expiresIn: LAB_SESSION_MAX_AGE_MS });
    const response = json({ ok: true }, 200);
    response.cookies.set(LAB_SESSION_COOKIE, cookie, cookieOptions);
    return response;
  } catch {
    return json({ error: "Unable to create session" }, 401);
  }
}

export async function GET(request: NextRequest) {
  if (!isLabEnabled()) return json({ error: "Not found" }, 404);
  const ownerUid = getOwnerUid();
  const cookie = request.cookies.get(LAB_SESSION_COOKIE)?.value;
  if (!ownerUid || !cookie) return json({ authenticated: false }, 401);
  try {
    const decoded = await getLabAdminAuth().verifySessionCookie(cookie, true);
    if (decoded.uid !== ownerUid) return json({ authenticated: false }, 403);
    return json({ authenticated: true }, 200);
  } catch {
    return json({ authenticated: false }, 401);
  }
}

export async function DELETE(request: NextRequest) {
  if (!isLabEnabled()) return json({ error: "Not found" }, 404);
  if (!hasSameOrigin(request)) return json({ error: "Invalid request origin" }, 403);
  const response = json({ ok: true }, 200);
  response.cookies.set(LAB_SESSION_COOKIE, "", { ...cookieOptions, maxAge: 0 });
  return response;
}
