import { NextRequest, NextResponse } from "next/server";
import { hasSameOrigin } from "../../../../../lib/portfolio-lab/session-origin";
import { hasLabJsonContent, readLabJson } from "../../../../../lib/portfolio-lab/request-json";
import {
  WORKFORCE_COOKIE, WORKFORCE_COOKIE_PATH, WORKFORCE_SESSION_TTL,
  workforceBackendOrigin, workforceEnabled,
} from "../../../../../lib/portfolio-lab/workforce-password-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function json(data: object, status = 200) {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

async function backend(path: string, init: RequestInit) {
  return fetch(`${workforceBackendOrigin()}/api/workforce-access/${path}`, {
    ...init, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000),
  });
}

export async function GET(request: NextRequest) {
  if (!workforceEnabled()) return json({ detail: "Not found" }, 404);
  const session = request.cookies.get(WORKFORCE_COOKIE)?.value;
  if (!session) return json({ authenticated: false });
  try {
    const upstream = await backend("session", { headers: { Authorization: `WorkforceDemo ${session}` } });
    if (!upstream.ok) return json({ detail: "Access service unavailable" }, 503);
    const body: unknown = await upstream.json();
    if (!body || typeof body !== "object" || !("authenticated" in body) ||
        typeof body.authenticated !== "boolean") return json({ detail: "Invalid access response" }, 502);
    return json({ authenticated: body.authenticated });
  } catch {
    return json({ detail: "Access service unavailable" }, 503);
  }
}

export async function POST(request: NextRequest) {
  if (!workforceEnabled()) return json({ detail: "Not found" }, 404);
  if (!hasSameOrigin(request)) return json({ detail: "Origin not allowed" }, 403);
  if (!hasLabJsonContent(request)) return json({ detail: "Send application/json" }, 415);
  const body = await readLabJson(request, 512);
  if (body === "too_large") return json({ detail: "Request too large" }, 413);
  if (!body || typeof body.password !== "string" || body.password.length < 1 ||
      body.password.length > 128 || Object.keys(body).some((key) => key !== "password")) {
    return json({ detail: "Invalid password request" }, 422);
  }
  try {
    const upstream = await backend("login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: body.password }),
    });
    if (!upstream.ok) {
      if ([401, 429, 503].includes(upstream.status)) {
        const message = upstream.status === 401 ? "Incorrect password" :
          upstream.status === 429 ? "Too many attempts. Retry in one minute." : "Access service unavailable";
        return json({ detail: message }, upstream.status);
      }
      return json({ detail: "Access service unavailable" }, 502);
    }
    const value: unknown = await upstream.json();
    if (!value || typeof value !== "object" || !("session" in value) ||
        typeof value.session !== "string" || !/^v1\.\d+\.[0-9a-f]{64}$/.test(value.session)) {
      return json({ detail: "Invalid access response" }, 502);
    }
    const response = json({ ok: true });
    response.cookies.set(WORKFORCE_COOKIE, value.session, {
      httpOnly: true, secure: request.nextUrl.protocol === "https:",
      sameSite: "strict", path: WORKFORCE_COOKIE_PATH, maxAge: WORKFORCE_SESSION_TTL,
    });
    return response;
  } catch {
    return json({ detail: "Access service unavailable" }, 503);
  }
}

export function DELETE(request: NextRequest) {
  if (!workforceEnabled()) return json({ detail: "Not found" }, 404);
  if (!hasSameOrigin(request)) return json({ detail: "Origin not allowed" }, 403);
  const response = json({ ok: true });
  response.cookies.delete({ name: WORKFORCE_COOKIE, path: WORKFORCE_COOKIE_PATH });
  return response;
}
