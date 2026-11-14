import { NextRequest, NextResponse } from "next/server";
import {
  getLabAdminAuth,
  getOwnerUid,
  isLabEnabled,
  LAB_SESSION_COOKIE,
  LAB_SESSION_MAX_AGE_MS,
} from "../../../lib/portfolio-lab/firebase-server";
import { hasSameOrigin } from "../../../lib/portfolio-lab/session-origin";
import { getLabAdmissionDecision } from "../../../lib/portfolio-lab/lab-admission-server";
import { hasLabJsonContent, readLabJson } from "../../../lib/portfolio-lab/request-json";
import { isRecentLabLogin } from "../../../lib/portfolio-lab/session-policy";

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
  if (!hasSameOrigin(request) || !hasLabJsonContent(request)) {
    return json({ error: "Invalid request origin or content type" }, 403);
  }
  const ownerUid = getOwnerUid();
  if (!ownerUid) return json({ error: "Lab unavailable" }, 503);
  const body = await readLabJson(request, 10_000);
  if (body === "too_large") return json({ error: "Request too large" }, 413);
  const idToken = body?.idToken;
  if (typeof idToken !== "string" || !idToken || idToken.length > 8192) {
    return json({ error: "Invalid token" }, 400);
  }
  try {
    const admin = await getLabAdminAuth();
    const decoded = await admin.verifyIdToken(idToken, true);
    if (!isRecentLabLogin(decoded.auth_time)) {
      return json({ error: "Recent login required" }, 403);
    }
    let admission;
    try {
      admission = await getLabAdmissionDecision(decoded);
    } catch {
      return json({ error: "Admission service unavailable" }, 503);
    }
    if (admission !== "allowed") return json({ error: "Access denied" }, 403);
    // PR 3 adds project capabilities; admitted identity does not grant project access.
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
  let decoded;
  try {
    const admin = await getLabAdminAuth();
    decoded = await admin.verifySessionCookie(cookie, true);
  } catch {
    return json({ authenticated: false }, 401);
  }
  try {
    const decision = await getLabAdmissionDecision(decoded);
    if (decision !== "allowed") return json({ authenticated: false }, 403);
  } catch {
    return json({ authenticated: false }, 503);
  }
  return json({ authenticated: true, canLink: isRecentLabLogin(decoded.auth_time) }, 200);
}

export async function DELETE(request: NextRequest) {
  if (!isLabEnabled()) return json({ error: "Not found" }, 404);
  if (!hasSameOrigin(request)) return json({ error: "Invalid request origin" }, 403);
  const response = json({ ok: true }, 200);
  response.cookies.set(LAB_SESSION_COOKIE, "", { ...cookieOptions, maxAge: 0 });
  return response;
}
