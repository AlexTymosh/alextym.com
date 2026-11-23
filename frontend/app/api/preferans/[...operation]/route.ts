import { NextRequest, NextResponse } from "next/server";
import { isLabEnabled, LAB_SESSION_COOKIE } from "../../../../lib/portfolio-lab/firebase-server";
import { labProjectAccess } from "../../../../lib/portfolio-lab/project-access-server";
import { hasSameOrigin } from "../../../../lib/portfolio-lab/session-origin";
import { workforceBackendOrigin } from "../../../../lib/portfolio-lab/workforce-password-server";
import { hasLabJsonContent, readLabJson } from "../../../../lib/portfolio-lab/request-json";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function response(status: number, data: object) {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

function upstreamPath(method: string, parts: string[]): string | null {
  if (parts.length === 1 && parts[0] === "rooms" && method === "POST") return "/api/preferans/rooms";
  if (parts.length !== 3 || parts[0] !== "rooms" || !/^[a-f0-9]{32}$/.test(parts[1])) return null;
  const allowed: Record<string, string[]> = {
    join: ["POST"], start: ["POST"], commands: ["POST"], settle: ["POST"],
    view: ["GET"], events: ["GET"],
  };
  if (!allowed[parts[2]]?.includes(method)) return null;
  return `/api/preferans/rooms/${parts[1]}/${parts[2]}`;
}

async function forward(request: NextRequest, { params }: { params: Promise<{ operation: string[] }> }) {
  const { operation } = await params;
  const path = upstreamPath(request.method, operation);
  if (!path || !isLabEnabled() || process.env.PREFERANS_ROOMS_ENABLED !== "true") {
    return response(404, { detail: "Not found" });
  }
  if (request.method !== "GET" && !hasSameOrigin(request)) {
    return response(403, { detail: "Origin not allowed" });
  }
  const session = request.cookies.get(LAB_SESSION_COOKIE)?.value;
  if (!session) return response(401, { detail: "Sign in required" });
  try {
    const access = await labProjectAccess(session, "preferans", request.method, path);
    if (access.status !== 200) return response(access.status, { detail: "Project access denied" });
  } catch {
    return response(503, { detail: "Access unavailable" });
  }

  const headers = new Headers({ Authorization: `FirebaseSession ${session}`, Accept: "application/json" });
  let body: string | undefined;
  if (request.method === "POST") {
    if (!hasLabJsonContent(request)) return response(415, { detail: "JSON required" });
    const data = await readLabJson(request, 8192);
    if (!data || data === "too_large" || Array.isArray(data)) {
      return response(data === "too_large" ? 413 : 422, { detail: "Invalid JSON" });
    }
    body = JSON.stringify(data);
    headers.set("Content-Type", "application/json");
  }
  try {
    const isEvents = path.endsWith("/events");
    const isView = path.endsWith("/view");
    const query = isEvents || isView ? request.nextUrl.searchParams : new URLSearchParams();
    if (query.size > 1 || Array.from(query.keys()).some(k =>
        k !== (isEvents ? "limit" : isView ? "since_version" : ""))) {
      return response(422, { detail: "Invalid query" });
    }
    const upstream = await fetch(workforceBackendOrigin() + path + (query.size ? `?${query}` : ""), {
      method: request.method, headers, body, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(25000),
    });
    if (![200, 201, 401, 403, 404, 409, 413, 422, 503].includes(upstream.status)) {
      return response(502, { detail: "Invalid upstream status" });
    }
    const data: unknown = await upstream.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      return response(502, { detail: "Invalid upstream response" });
    }
    return response(upstream.status, data);
  } catch {
    return response(502, { detail: "Game service unavailable" });
  }
}

export { forward as GET, forward as POST };
