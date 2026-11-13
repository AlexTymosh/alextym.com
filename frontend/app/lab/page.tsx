import type { Metadata } from "next";
import type { DecodedIdToken } from "firebase-admin/auth";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { LabAccountActions } from "../../components/lab-account-actions";
import { getLabAdmissionDecision } from "../../lib/portfolio-lab/lab-admission-server";
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
  if (!getOwnerUid()) notFound();
  let verifiedClaims: DecodedIdToken;
  try {
    verifiedClaims = await getLabAdminAuth().verifySessionCookie(cookie, true);
  } catch {
    redirect("/lab/login");
  }
  let admission;
  try {
    admission = await getLabAdmissionDecision(verifiedClaims);
  } catch {
    // Never fall back to a privileged cached identity on Firestore failure.
    notFound();
  }
  if (admission !== "allowed") redirect("/lab/login");
  return (
    <section style={{ maxWidth: 660, margin: "4rem auto", padding: "1rem" }}>
      <h1>Portfolio Lab — Identity preview</h1>
      <p>Authenticated identity preview. Project access and administration remain disabled until the RBAC release.</p>
      <LabAccountActions />
    </section>
  );
}
