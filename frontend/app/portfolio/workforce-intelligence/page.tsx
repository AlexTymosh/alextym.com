import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { WorkforcePasswordGate } from "@workforce-intelligence";
import { workforceEnabled } from "../../../lib/portfolio-lab/workforce-password-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { absolute: "Workforce & Recruitment Intelligence — Demo" },
  icons: { icon: "/workforce-simulation-logo.png" },
  robots: { index: false, follow: false },
};

export default function WorkforceIntelligencePage() {
  if (!workforceEnabled()) notFound();
  return <WorkforcePasswordGate />;
}
