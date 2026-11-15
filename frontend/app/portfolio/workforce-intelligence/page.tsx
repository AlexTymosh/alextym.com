import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { WorkforcePasswordGate } from "@workforce-intelligence";
import { workforceEnabled } from "../../../lib/portfolio-lab/workforce-password-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Workforce & Recruitment Intelligence — Demo",
  robots: { index: false, follow: false },
};

export default function WorkforceIntelligencePage() {
  if (!workforceEnabled()) notFound();
  return <WorkforcePasswordGate />;
}
