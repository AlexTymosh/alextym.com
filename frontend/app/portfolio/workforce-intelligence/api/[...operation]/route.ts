import type { NextRequest } from "next/server";
import { forwardWorkforceRequest } from "../../../../../lib/portfolio-lab/workforce-bff-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function forward(request: NextRequest, { params }: { params: Promise<{ operation: string[] }> }) {
  return forwardWorkforceRequest(request, (await params).operation);
}

export { forward as GET, forward as PATCH, forward as POST };
