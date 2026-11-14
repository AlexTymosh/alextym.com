import { NextRequest, NextResponse } from "next/server";
import { getWorkforceAccess } from "../../../../../lib/portfolio-lab/workforce-access-server";
import { LAB_SESSION_COOKIE } from "../../../../../lib/portfolio-lab/firebase-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function reply(status: number, body: object) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

/** Fixed destination: never accept a browser-supplied URL, host or project ID. */
function backendOrigin(): string {
  const raw = process.env.BACKEND_ORIGIN?.trim();
  if (!raw) throw new Error("Backend origin missing");
  const url = new URL(raw);
  if (!["https:", "http:"].includes(url.protocol) ||
      (process.env.NODE_ENV === "production" && url.protocol !== "https:") ||
      (url.pathname !== "/" && url.pathname !== "") || url.username || url.password ||
      url.search || url.hash) throw new Error("Invalid backend origin");
  return url.origin;
}

export async function GET(request: NextRequest) {
  const sessionCookie = request.cookies.get(LAB_SESSION_COOKIE)?.value;
  const access = await getWorkforceAccess(sessionCookie);
  if (access.kind === "disabled") return reply(404, { error: "Not found" });
  if (access.kind === "unauthenticated") return reply(401, { error: "Authentication required" });
  if (access.kind === "denied") return reply(403, { error: "Project access denied" });
  if (access.kind === "unavailable") return reply(503, { error: "Access unavailable" });

  try {
    const url = new URL("/api/workforce/status", backendOrigin());
    const upstream = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `FirebaseSession ${sessionCookie}`,
        Accept: "application/json",
      },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(25_000),
    });
    if (!upstream.ok) {
      if ([401, 403, 404, 503].includes(upstream.status)) {
        return reply(upstream.status, { error: "Backend authorization failed" });
      }
      return reply(502, { error: "Backend unavailable" });
    }
    const data: unknown = await upstream.json();
    if (!data || typeof data !== "object" ||
        !("service" in data) || data.service !== "workforce" ||
        !("available" in data) || data.available !== true) {
      return reply(502, { error: "Invalid backend response" });
    }
    return reply(200, { available: true, service: "workforce" });
  } catch {
    return reply(502, { error: "Backend unavailable" });
  }
}
