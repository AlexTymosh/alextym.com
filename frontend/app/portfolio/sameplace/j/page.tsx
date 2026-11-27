import { notFound } from "next/navigation";
import { isLabEnabled } from "../../../../lib/portfolio-lab/firebase-server";
import { SamePlaceInvitationClient } from "../client";
export const dynamic = "force-dynamic";
export const metadata = { title: "SamePlace", robots: { index: false, follow: false }, referrer: "no-referrer" as const };
export default function InvitePage() {
  if (!isLabEnabled() || process.env.SAMEPLACE_ENABLED !== "true") notFound();
  return <SamePlaceInvitationClient />;
}
