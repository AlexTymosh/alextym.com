import { NextRequest, NextResponse } from "next/server";
import { getOwnerUid, isLabEnabled, LAB_SESSION_COOKIE } from "../../../../lib/portfolio-lab/firebase-server";
import { labSession } from "../../../../lib/portfolio-lab/project-access-server";
import { isRecentLabLogin } from "../../../../lib/portfolio-lab/session-policy";
import { hasSameOrigin } from "../../../../lib/portfolio-lab/session-origin";
import { hasLabJsonContent, readLabJson } from "../../../../lib/portfolio-lab/request-json";
import { grantChange } from "../../../../lib/portfolio-lab/grant-change";
import { changeLabGrant } from "../../../../lib/portfolio-lab/owner-access-server";
import { labProjects } from "../../../../lib/portfolio-lab/project-catalog";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const reply = (status: number, data: object = {}) =>
  NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });

export async function POST(request: NextRequest) {
  if (!isLabEnabled()) return reply(404);
  if (!hasSameOrigin(request) || !hasLabJsonContent(request)) return reply(403);
  try {
    const session = await labSession(request.cookies.get(LAB_SESSION_COOKIE)?.value).catch(() => null);
    if (!session) return reply(401);
    if (session.uid !== getOwnerUid()) return reply(403);
    if (!isRecentLabLogin(session.auth_time)) return reply(403, { code: "RECENT_LOGIN_REQUIRED" });
    const body = await readLabJson(request, 2048);
    if (body === "too_large") return reply(413);
    const change = grantChange(body, labProjects.map((project) => project.id));
    if (!change) return reply(400);
    const result = await changeLabGrant(change, session.uid);
    return reply(result.status, { revision: result.revision });
  } catch {
    return reply(503);
  }
}
