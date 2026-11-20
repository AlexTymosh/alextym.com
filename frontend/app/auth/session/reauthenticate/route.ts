import { NextRequest, NextResponse } from "next/server";
import { getLabAdminAuth, getOwnerUid, isLabEnabled, LAB_SESSION_COOKIE,
  LAB_SESSION_COOKIE_OPTIONS, LAB_SESSION_MAX_AGE_MS } from "../../../../lib/portfolio-lab/firebase-server";
import { getLabAdmissionDecision } from "../../../../lib/portfolio-lab/lab-admission-server";
import { hasLabJsonContent, readLabJson } from "../../../../lib/portfolio-lab/request-json";
import { hasSameOrigin } from "../../../../lib/portfolio-lab/session-origin";
import { isMatchingRecentLogin } from "../../../../lib/portfolio-lab/session-policy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const reply = (status: number, data: object = {}) =>
  NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });

export async function POST(request: NextRequest) {
  if (!isLabEnabled()) return reply(404);
  if (!hasSameOrigin(request) || !hasLabJsonContent(request)) return reply(403);
  if (!getOwnerUid()) return reply(503);
  const cookie = request.cookies.get(LAB_SESSION_COOKIE)?.value;
  if (!cookie) return reply(401);
  const body = await readLabJson(request, 10_000);
  if (body === "too_large") return reply(413);
  if (typeof body?.idToken !== "string" || !body.idToken || body.idToken.length > 8192) return reply(400);
  try {
    const admin = await getLabAdminAuth();
    const [session, proof] = await Promise.all([
      admin.verifySessionCookie(cookie, true), admin.verifyIdToken(body.idToken, true),
    ]);
    if (!isMatchingRecentLogin(session, proof)) return reply(403);
    try {
      // A newly linked but unconfirmed provider cannot authorize this refresh.
      const decisions = await Promise.all([
        getLabAdmissionDecision(session), getLabAdmissionDecision(proof),
      ]);
      if (decisions.some((decision) => decision !== "allowed")) return reply(403);
    } catch { return reply(503); }
    const refreshed = await admin.createSessionCookie(body.idToken, { expiresIn: LAB_SESSION_MAX_AGE_MS });
    const response = reply(200, { authTime: proof.auth_time });
    response.cookies.set(LAB_SESSION_COOKIE, refreshed, LAB_SESSION_COOKIE_OPTIONS);
    return response;
  } catch { return reply(401); }
}
