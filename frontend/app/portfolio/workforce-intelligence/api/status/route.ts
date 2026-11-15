import type { NextRequest } from "next/server";
import { forwardWorkforceRequest } from "../../../../../lib/portfolio-lab/workforce-bff-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  return forwardWorkforceRequest(request, ["status"]);
}
