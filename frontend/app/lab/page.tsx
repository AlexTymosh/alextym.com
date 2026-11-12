import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { LabAccountActions } from "../../components/lab-account-actions";
import {
  getLabAdminAuth,
  getOwnerUid,
  isLabEnabled,
  LAB_SESSION_COOKIE,
} from "../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Portfolio Lab", robots: { index: false, follow: false } };

export default async function LabPage() {
  if (!isLabEnabled()) notFound();
  const cookie = (await cookies()).get(LAB_SESSION_COOKIE)?.value;
  if (!cookie) redirect("/lab/login");
  let verifiedUid = "";
  try {
    verifiedUid = (await getLabAdminAuth().verifySessionCookie(cookie, true)).uid;
  } catch {
    redirect("/lab/login");
  }
  if (!getOwnerUid() || verifiedUid !== getOwnerUid()) redirect("/lab/login");
  return (
    <section style={{ maxWidth: 660, margin: "4rem auto", padding: "1rem" }}>
      <h1>Portfolio Lab — Identity preview</h1>
      <p>Owner authentication is active. Project access and administration remain disabled until the RBAC release.</p>
      <LabAccountActions />
    </section>
  );
}
