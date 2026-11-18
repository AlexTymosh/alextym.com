import type { Metadata } from "next";
import type { DecodedIdToken } from "firebase-admin/auth";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { LabAccountActions } from "../../components/lab-account-actions";
import styles from "../../components/lab-auth.module.css";
import { isLabOAuthProvider, labSignInProvider } from "../../lib/portfolio-lab/admission-policy";
import { labProviderNames } from "../../lib/portfolio-lab/auth-ui";
import { getLabAdmissionDecision, getLabLinkedProviders } from "../../lib/portfolio-lab/lab-admission-server";
import { labProjects } from "../../lib/portfolio-lab/project-catalog";
import { labProjectRole } from "../../lib/portfolio-lab/project-access-server";
import {
  getLabAdminAuth,
  getOwnerUid,
  isLabEnabled,
  LAB_SESSION_COOKIE,
} from "../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Your account", robots: { index: false, follow: false } };

export default async function LabPage() {
  if (!isLabEnabled()) notFound();
  const cookie = (await cookies()).get(LAB_SESSION_COOKIE)?.value;
  if (!cookie) redirect("/lab/login");
  if (!getOwnerUid()) notFound();
  let verifiedClaims: DecodedIdToken;
  try {
    const admin = await getLabAdminAuth();
    verifiedClaims = await admin.verifySessionCookie(cookie, true);
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
  const provider = labSignInProvider(verifiedClaims);
  const signInMethod = isLabOAuthProvider(provider) ? labProviderNames[provider] : "email and password";
  const linkedProviders = await getLabLinkedProviders(verifiedClaims.uid).catch(() => null);
  const isOwner = verifiedClaims.uid === getOwnerUid();
  const projectAccess = await Promise.all(labProjects.map(async (project) => ({
    ...project, role: await labProjectRole(verifiedClaims.uid, project.id),
  }))).catch(() => null);
  const available = projectAccess?.filter((project) => project.role) ?? [];

  return (
    <section className={`${styles.panel} ${styles.accountPanel}`} aria-labelledby="lab-account-title">
      <header className={styles.header}>
        <h1 id="lab-account-title">Your account</h1>
        <p>Signed in with <strong className={styles.signInMethod}>{signInMethod}</strong></p>
      </header>
      <section className={styles.accountActions} aria-labelledby="lab-projects">
        <h2 id="lab-projects">Your access</h2>
        {projectAccess === null ? <p className={styles.notice} role="alert">Access information is temporarily unavailable. Reload to retry.</p> :
          available.length === 0 ? <p className={styles.notice} role="status">No access has been assigned to your account.</p> :
          <ul className={styles.providerList}>
            {available.map((project) => (
              <li key={project.id} className={styles.userCard}>
                <h3 className={styles.providerLabel}>{project.title}</h3>
                <p className={styles.hint}>{project.role} access</p>
                <Link className={styles.secondaryButton} href={project.path}>Open</Link>
              </li>
            ))}
          </ul>
        }
        <Link className={styles.textAction} href="/lab">Refresh access</Link>
      </section>
      {isOwner && <Link className={styles.primaryButton} href="/lab/admin">Manage access</Link>}
      <LabAccountActions linkedProviders={linkedProviders} />
    </section>
  );
}
