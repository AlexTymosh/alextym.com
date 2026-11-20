import { notFound, redirect } from "next/navigation";
import { isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata = { robots: { index: false, follow: false } };

export default async function LegacyAccountPage({ searchParams }: { searchParams: Promise<{ after?: string }> }) {
  if (!isLabEnabled()) notFound();
  const { after } = await searchParams;
  if (after) redirect("/settings/access?after=" + encodeURIComponent(after));
  redirect("/settings/access");
}
