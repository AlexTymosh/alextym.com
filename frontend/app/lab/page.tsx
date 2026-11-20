import { notFound, redirect } from "next/navigation";
import { isLabEnabled } from "../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata = { robots: { index: false, follow: false } };

export default async function LegacyAccountPage() {
  if (!isLabEnabled()) notFound();
  redirect("/settings");
}
