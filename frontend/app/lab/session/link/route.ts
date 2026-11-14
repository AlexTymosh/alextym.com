import { NextRequest, NextResponse } from "next/server";
import { isLabOAuthProvider } from "../../../../lib/portfolio-lab/admission-policy";
import {
  getLabAdminAuth,
  getOwnerUid,
  isLabEnabled,
  LAB_SESSION_COOKIE,
} from "../../../../lib/portfolio-lab/firebase-server";
import { confirmLabProviderLink } from "../../../../lib/portfolio-lab/provider-link-server";
import { hasLabJsonContent, readLabJson } from "../../../../lib/portfolio-lab/request-json";
import { hasSameOrigin } from "../../../../lib/portfolio-lab/session-origin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function reply(status: number) {
  return NextResponse.json({ ok: status === 200 }, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(request: NextRequest) {
  if (!isLabEnabled()) return reply(404);
  if (!hasSameOrigin(request) || !hasLabJsonContent(request)) return reply(403);
  const ownerUid = getOwnerUid();
  if (!ownerUid) return reply(503);
  const cookie = request.cookies.get(LAB_SESSION_COOKIE)?.value;
  if (!cookie) return reply(401);
  const body = await readLabJson(request, 10_000);
  if (body === "too_large") return reply(413);
  if (!isLabOAuthProvider(body?.provider) || typeof body?.idToken !== "string" ||
      !body.idToken || body.idToken.length > 8192) return reply(400);

  let session;
  let proof;
  try {
    const admin = getLabAdminAuth();
    [session, proof] = await Promise.all([
      admin.verifySessionCookie(cookie, true),
      admin.verifyIdToken(body.idToken, true),
    ]);
  } catch {
    return reply(401);
  }
  try {
    return reply(await confirmLabProviderLink(session, proof, body.provider, ownerUid) ? 200 : 403);
  } catch {
    return reply(503);
  }
}
