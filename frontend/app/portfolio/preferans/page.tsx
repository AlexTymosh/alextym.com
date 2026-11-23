import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PreferansWelcome } from "@preferans";
import { isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { requireLabProjectPage } from "../../../lib/portfolio-lab/project-access-server";

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
  return <PreferansWelcome />;
}
