import { notFound } from "next/navigation";
import { validRoomSlug } from "@sameplace";
import { isLabEnabled } from "../../../../../lib/portfolio-lab/firebase-server";
import { SamePlaceClient } from "../../client";
export const dynamic = "force-dynamic";
export const metadata = { title: "SamePlace", robots: { index: false, follow: false }, referrer: "no-referrer" as const };
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  if (!isLabEnabled() || process.env.SAMEPLACE_ENABLED !== "true") notFound();
  const { slug } = await params;
  if (!validRoomSlug(slug)) notFound();
  return <SamePlaceClient slug={slug} />;
}
