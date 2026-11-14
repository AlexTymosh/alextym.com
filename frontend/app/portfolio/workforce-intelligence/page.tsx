import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { WorkforceScaffold } from "@workforce-intelligence";
import { LAB_SESSION_COOKIE } from "../../../lib/portfolio-lab/firebase-server";
import { getWorkforceAccess } from "../../../lib/portfolio-lab/workforce-access-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Workforce & Recruitment Intelligence — Demo",
  robots: { index: false, follow: false },
};

export default async function WorkforceIntelligencePage() {
  const cookie = (await cookies()).get(LAB_SESSION_COOKIE)?.value;
  const access = await getWorkforceAccess(cookie);
  if (access.kind === "unauthenticated") redirect("/lab/login");
  if (access.kind !== "allowed") notFound();
  return <WorkforceScaffold />;
}
