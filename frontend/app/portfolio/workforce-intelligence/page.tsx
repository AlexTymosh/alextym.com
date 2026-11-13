import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const metadata: Metadata = {
  title: "Workforce & Recruitment Intelligence — Demo",
  robots: { index: false, follow: false },
};

/** No authz shortcut: implement the shared grant guard before mounting the UI. */
export default function WorkforceIntelligencePage() {
  notFound();
}
