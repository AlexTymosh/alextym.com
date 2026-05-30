import type { NextRequest } from "next/server";
import { getResumeData } from "../../../content/resume";
import {
  buildResumePdf,
  getResumePdfFileName,
  parseResumePdfOptions,
} from "../../../content/resume-pdf";

export const runtime = "nodejs";

export function GET(request: NextRequest): Response {
  const options = parseResumePdfOptions(request.nextUrl.searchParams);
  const fileName = getResumePdfFileName();
  const pdf = buildResumePdf(getResumeData(), options);

  return new Response(toArrayBuffer(pdf), {
    headers: {
      "Cache-Control": "no-store",
      "Content-Disposition": `attachment; filename="${fileName}"`,
      "Content-Type": "application/pdf",
    },
  });
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const arrayBuffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(arrayBuffer).set(bytes);

  return arrayBuffer;
}
