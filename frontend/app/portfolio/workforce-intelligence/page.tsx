import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { WorkforcePasswordGate } from "@workforce-intelligence";
import { workforceEnabled } from "../../../lib/portfolio-lab/workforce-password-server";
import { isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { requireLabProjectPage } from "../../../lib/portfolio-lab/project-access-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { absolute: "Workforce & Recruitment Intelligence — Demo" },
  icons: { icon: "/workforce-simulation-logo.png" },
  robots: { index: false, follow: false },
};

export default async function WorkforceIntelligencePage() {
  if (!workforceEnabled()) notFound();
  await requireLabProjectPage("workforce_intelligence");
  return <WorkforcePasswordGate loginPath={isLabEnabled() ? "/lab/login" : undefined} />;
}
