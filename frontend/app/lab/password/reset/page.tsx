import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LabPasswordReset } from "../../../../components/lab-password-reset";
import { isLabEnabled } from "../../../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Portfolio Lab password setup",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function LabPasswordResetPage() {
  if (!isLabEnabled()) notFound();
  return <LabPasswordReset />;
}
