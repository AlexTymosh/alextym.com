import { NextRequest, NextResponse } from "next/server";
import { isLabEnabled, LAB_SESSION_COOKIE } from "../../../../lib/portfolio-lab/firebase-server";
import { labProjectAccess } from "../../../../lib/portfolio-lab/project-access-server";
import { hasSameOrigin } from "../../../../lib/portfolio-lab/session-origin";
import { workforceBackendOrigin } from "../../../../lib/portfolio-lab/workforce-password-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function reply(status: number, data: object) {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

async function forward(request: NextRequest, { params }: { params: Promise<{ operation: string[] }> }) {
  const { operation } = await params;
  if (!operation.length || !operation.every((part) => /^[a-zA-Z0-9_.-]{1,128}$/.test(part) && part !== "." && part !== "..")) {
    return reply(404, { detail: "Not found" });
  }
  const path = "/api/vor/" + operation.join("/");
  const lab = isLabEnabled();
  if (lab && path === "/api/vor/login") return reply(404, { detail: "Not found" });
  if (lab && request.method !== "GET" && !hasSameOrigin(request)) return reply(403, { detail: "Origin not allowed" });
  const headers = new Headers();
  let role: string | null = null;
  if (lab) {
    const cookie = request.cookies.get(LAB_SESSION_COOKIE)?.value;
    try {
      const access = await labProjectAccess(cookie, "fleet_hub", request.method, path);
      if (access.status !== 200) return reply(access.status, { detail: "Project access required" });
      role = access.role;
      if (path === "/api/vor/logout" && request.method === "POST") {
        const response = reply(200, { ok: true });
        response.cookies.set(LAB_SESSION_COOKIE, "", {
          httpOnly: true, secure: process.env.NODE_ENV === "production",
          sameSite: "strict", path: "/", maxAge: 0,
        });
        return response;
      }
      headers.set("Authorization", `FirebaseSession ${cookie}`);
    } catch {
      return reply(503, { detail: "Project access unavailable" });
    }
  } else {
    for (const name of ["Cookie", "Origin", "Content-Type"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    headers.set("X-Forwarded-Host", request.headers.get("host") ?? request.nextUrl.host);
    headers.set("X-Forwarded-Proto", request.nextUrl.protocol.slice(0, -1));
  }
  if (request.headers.get("content-type")) headers.set("Content-Type", request.headers.get("content-type")!);
  try {
    const init: RequestInit & { duplex?: "half" } = {
      method: request.method, headers, cache: "no-store", redirect: "manual",
      signal: AbortSignal.timeout(55_000),
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body;
      init.duplex = "half";
    }
    const response = await fetch(workforceBackendOrigin() + path + request.nextUrl.search, init);
    if (lab && path === "/api/vor/session" && response.ok) {
      const session = await response.json();
      return reply(200, { enabled: session.enabled === true, authenticated: true, liveEmail: session.liveEmail === true, role });
    }
    const output = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["Content-Type", "Content-Disposition", "Retry-After", "X-Request-ID"]) {
      const value = response.headers.get(name);
      if (value) output.set(name, value);
    }
    if (!lab) for (const cookie of response.headers.getSetCookie()) output.append("Set-Cookie", cookie);
    return new NextResponse(response.body, { status: response.status, headers: output });
  } catch {
    return reply(502, { detail: "Fleet service unavailable" });
  }
}

export { forward as GET, forward as POST, forward as PATCH, forward as PUT, forward as DELETE };
