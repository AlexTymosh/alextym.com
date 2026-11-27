import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SamePlaceFoundation } from "@sameplace";
import { isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { requireLabProjectPage } from "../../../lib/portfolio-lab/project-access-server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { absolute: "SamePlace" },
  robots: { index: false, follow: false },
};

export default async function SamePlacePage() {
  if (!isLabEnabled() || process.env.SAMEPLACE_ENABLED !== "true") notFound();
  await requireLabProjectPage("sameplace");
  return <SamePlaceFoundation />;
}
