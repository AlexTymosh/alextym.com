import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { SamePlaceClient } from "./client";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { absolute: "SamePlace" },
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function SamePlacePage() {
  if (!isLabEnabled() || process.env.SAMEPLACE_ENABLED !== "true") notFound();
  // The shell contains no room metadata. All private projections are independently guarded.
  return <SamePlaceClient />;
}
