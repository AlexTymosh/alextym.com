import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LabLogin } from "../../../components/lab-login";
import { isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";

export const metadata: Metadata = { title: "Portfolio Lab sign in", robots: { index: false, follow: false } };

export default function LabLoginPage() {
  if (!isLabEnabled()) notFound();
  return <LabLogin />;
}
