import type { Metadata } from "next";
import { createHash } from "node:crypto";
import { notFound } from "next/navigation";
import { PreferansGame, PreferansWelcome } from "@preferans";
import { isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { currentLabSession, requireLabProjectPage } from "../../../lib/portfolio-lab/project-access-server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { absolute: "Zaporizhzhia Preferans — Private Demo" },
  description: "A private three-player Preferans project under development.",
  robots: { index: false, follow: false },
};

export default async function PreferansPage() {
  // requireLabProjectPage is intentionally a no-op when Lab is disabled.
  // Explicit 404 prevents the shell from becoming public in that mode.
  if (!isLabEnabled()) notFound();
  await requireLabProjectPage("preferans");
  if (process.env.PREFERANS_ROOMS_ENABLED !== "true") return <PreferansWelcome />;
  const session = await currentLabSession();
  // Only an opaque local preference namespace is passed to the browser.
  const preferenceScope = session ? createHash("sha256").update("preferans-sort-v1\0" + session.uid).digest("hex") : undefined;
  return <PreferansGame preferenceScope={preferenceScope} />;
}
