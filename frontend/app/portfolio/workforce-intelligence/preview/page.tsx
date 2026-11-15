import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { WorkforceScaffold } from "@workforce-intelligence";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Workforce Intelligence — Local UI preview",
  robots: { index: false, follow: false },
};

/** Separate local inspection route. Never alter the protected app or API gates. */
export default function WorkforceLocalPreviewPage() {
  if (process.env.NODE_ENV !== "development" ||
      process.env.WORKFORCE_LOCAL_PREVIEW !== "true" ||
      Boolean(process.env.VERCEL)) {
    notFound();
  }
  return <WorkforceScaffold previewMode />;
}
