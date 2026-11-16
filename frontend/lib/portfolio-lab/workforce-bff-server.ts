import "server-only";

import { NextRequest, NextResponse } from "next/server";
import { WORKFORCE_COOKIE, workforceBackendOrigin, workforceEnabled } from "./workforce-password-server";
import { hasLabJsonContent, readLabJson } from "./request-json";
import { hasWorkforceOrigin } from "./workforce-origin";
import { workforceUpstreamPath } from "./workforce-transport";
import { hasWorkbookContent, readWorkbookBytes, XLSX_CONTENT_TYPE } from "./workforce-workbooks";

function reply(status: number, body: object, headers = new Headers()) {
  headers.set("Cache-Control", "no-store");
  return NextResponse.json(body, { status, headers });
}

export async function forwardWorkforceRequest(request: NextRequest, operation: string[]) {
  const path = workforceUpstreamPath(request.method, operation, request.nextUrl.searchParams);
  if (!path) return reply(404, { detail: "Not found" });

  if (!workforceEnabled()) return reply(404, { detail: "Not found" });
  const sessionCookie = request.cookies.get(WORKFORCE_COOKIE)?.value;
  if (!sessionCookie) return reply(401, { detail: "Password required" });

  const upload = path === "/api/workforce/import/validate";
  const download = path === "/api/workforce/export" || path === "/api/workforce/import/template" ||
    path.startsWith("/api/workforce/import/") && path.endsWith("/errors");
  const headers = new Headers({ Authorization: `WorkforceDemo ${sessionCookie}`,
    Accept: download ? XLSX_CONTENT_TYPE : "application/json" });
  let body: string | ArrayBuffer | undefined;
  if (request.method !== "GET") {
    if (!hasWorkforceOrigin(request)) return reply(403, { detail: "Origin not allowed" });
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
    const upstream = await fetch(new URL(path, workforceBackendOrigin()), {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(path.endsWith("/analyse") ? 55_000 : 25_000),
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
