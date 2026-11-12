import { NextRequest, NextResponse } from "next/server";
import {
  getLabAdminAuth,
  getOwnerUid,
  isLabEnabled,
  LAB_SESSION_COOKIE,
} from "../../../../lib/portfolio-lab/firebase-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const json = (status: number, error?: string) =>
  NextResponse.json(
    error ? { error } : { authenticated: true },
    { status, headers: { "Cache-Control": "no-store" } },
  );

/** Restrict outbound credentials to the fixed, explicitly configured backend. */
function getBackendOrigin(): string {
  const raw = process.env.BACKEND_ORIGIN?.trim();
  if (!raw) throw new Error("BACKEND_ORIGIN is missing");
  const parsed = new URL(raw);
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    (process.env.NODE_ENV === "production" && parsed.protocol !== "https:") ||
    (parsed.pathname !== "/" && parsed.pathname !== "") ||
    parsed.search ||
    parsed.hash ||
    parsed.username ||
    parsed.password
  ) {
    throw new Error("Invalid configured backend origin");
  }
  return parsed.origin;
}

export async function GET(request: NextRequest) {
  if (!isLabEnabled()) return json(404, "Not found");
  const ownerUid = getOwnerUid();
  if (!ownerUid) return json(503, "Lab unavailable");
  const cookie = request.cookies.get(LAB_SESSION_COOKIE)?.value;
  if (!cookie) return json(401, "Authentication required");

  let uid: string;
  try {
    uid = (await getLabAdminAuth().verifySessionCookie(cookie, true)).uid;
  } catch {
    return json(401, "Invalid session");
  }
  if (uid !== ownerUid) return json(403, "Access denied");

  let url: URL;
  try {
    url = new URL("/api/lab/identity", getBackendOrigin());
  } catch {
    return json(503, "Backend not configured");
  }
  try {
    const upstream = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `FirebaseSession ${cookie}`,
        Accept: "application/json",
      },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(25_000),
    });
    if (!upstream.ok) {
      if ([401, 403, 404, 503].includes(upstream.status)) {
        return json(upstream.status, "Backend authorization failed");
      }
      return json(502, "Backend unavailable");
    }
    const claims: unknown = await upstream.json();
    if (
      !claims ||
      typeof claims !== "object" ||
      !("uid" in claims) ||
      claims.uid !== uid
    ) {
      return json(502, "Backend identity mismatch");
    }
    return json(200);
  } catch {
    // Never expose the upstream body, provider exceptions or session cookie.
    return json(502, "Backend unavailable");
  }
}
