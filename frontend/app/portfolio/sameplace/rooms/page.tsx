import { notFound } from "next/navigation";
import { isLabEnabled } from "../../../../lib/portfolio-lab/firebase-server";
import { SamePlaceClient } from "../client";
export const dynamic = "force-dynamic";
export const metadata = { title: "SamePlace", robots: { index: false, follow: false }, referrer: "no-referrer" as const };
export default function RoomsPage() {
  if (!isLabEnabled() || process.env.SAMEPLACE_ENABLED !== "true") notFound();
  return <SamePlaceClient />;
}
