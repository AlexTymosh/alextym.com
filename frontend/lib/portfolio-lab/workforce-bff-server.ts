import "server-only";

import { NextRequest, NextResponse } from "next/server";
import { LAB_SESSION_COOKIE } from "./firebase-server";
import { hasLabJsonContent, readLabJson } from "./request-json";
import { hasSameOrigin } from "./session-origin";
import { getWorkforceAccess } from "./workforce-access-server";
import { workforceUpstreamPath } from "./workforce-transport";
import { hasWorkbookContent, readWorkbookBytes, XLSX_CONTENT_TYPE } from "./workforce-workbooks";

function reply(status: number, body: object, headers = new Headers()) {
  headers.set("Cache-Control", "no-store");
  return NextResponse.json(body, { status, headers });
}

function backendOrigin(): string {
  const raw = process.env.BACKEND_ORIGIN?.trim();
  if (!raw) throw new Error("Backend origin missing");
  const url = new URL(raw);
  if (!["https:", "http:"].includes(url.protocol) ||
      (process.env.NODE_ENV === "production" && url.protocol !== "https:") ||
      url.pathname !== "/" || url.username || url.password || url.search || url.hash) {
    throw new Error("Invalid backend origin");
  }
  return url.origin;
}

export async function forwardWorkforceRequest(request: NextRequest, operation: string[]) {
  const path = workforceUpstreamPath(request.method, operation, request.nextUrl.searchParams);
  if (!path) return reply(404, { detail: "Not found" });

  const sessionCookie = request.cookies.get(LAB_SESSION_COOKIE)?.value;
  const access = await getWorkforceAccess(sessionCookie);
  if (access.kind === "disabled") return reply(404, { detail: "Not found" });
  if (access.kind === "unauthenticated") return reply(401, { detail: "Authentication required" });
  if (access.kind === "denied") return reply(403, { detail: "Project access denied" });
  if (access.kind === "unavailable") return reply(503, { detail: "Access unavailable" });
  if (!sessionCookie) return reply(401, { detail: "Authentication required" });

  const upload = path === "/api/workforce/import/validate";
  const download = path === "/api/workforce/export" || path === "/api/workforce/import/template" ||
    path.startsWith("/api/workforce/import/") && path.endsWith("/errors");
  const headers = new Headers({ Authorization: `FirebaseSession ${sessionCookie}`,
    Accept: download ? XLSX_CONTENT_TYPE : "application/json" });
  let body: string | ArrayBuffer | undefined;
  if (request.method !== "GET") {
    if (!hasSameOrigin(request)) return reply(403, { detail: "Origin not allowed" });
    if (upload) {
      if (!hasWorkbookContent(request)) return reply(415, { detail: "Send an .xlsx workbook." });
      const bytes = await readWorkbookBytes(request);
      if (bytes === "too_large") return reply(413, { detail: "The workbook exceeds the 1 MiB upload limit." });
      if (!bytes) return reply(422, { detail: "The workbook was empty or incomplete." });
      headers.set("Content-Type", XLSX_CONTENT_TYPE);
      body = bytes;
    } else {
      if (!hasLabJsonContent(request)) return reply(415, { detail: "Send application/json" });
      const payload = await readLabJson(request, 4096);
      if (payload === "too_large") return reply(413, { detail: "Request too large" });
      if (!payload) return reply(422, { detail: "Invalid JSON request" });
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(payload);
    }
  }

  try {
    const upstream = await fetch(new URL(path, backendOrigin()), {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(25_000),
    });
    if (!upstream.ok && ![401, 403, 404, 409, 413, 415, 422, 429, 503].includes(upstream.status)) {
      return reply(502, { detail: "Backend unavailable" });
    }
    if (upstream.ok && download) {
      const disposition = upstream.headers.get("content-disposition") ?? "";
      if (!hasWorkbookContent(upstream) ||
          !/^attachment; filename="workforce-(template|import-issues|analytics|metrics|quality|survey)\.xlsx"$/.test(disposition)) {
        return reply(502, { detail: "Invalid workbook response" });
      }
      const bytes = await readWorkbookBytes(upstream);
      if (!bytes || bytes === "too_large") return reply(502, { detail: "Invalid workbook response" });
      return new NextResponse(bytes, { headers: {
        "Cache-Control": "no-store", "Content-Type": XLSX_CONTENT_TYPE,
        "Content-Disposition": disposition, "X-Content-Type-Options": "nosniff",
      } });
    }
    const data: unknown = await upstream.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      return reply(502, { detail: "Invalid backend response" });
    }
    if (path === "/api/workforce/status" && upstream.ok &&
        (!("service" in data) || data.service !== "workforce" ||
         !("available" in data) || data.available !== true)) {
      return reply(502, { detail: "Invalid backend response" });
    }
    const responseHeaders = new Headers();
    for (const name of ["X-Request-ID", "Retry-After"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    return reply(upstream.status, data, responseHeaders);
  } catch {
    return reply(502, { detail: "Backend unavailable" });
  }
}
