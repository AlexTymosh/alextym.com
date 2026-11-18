import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { currentLabSession } from "../../../lib/portfolio-lab/project-access-server";
import { getOwnerUid, isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { listLabUsers } from "../../../lib/portfolio-lab/owner-access-server";
import { labProjects } from "../../../lib/portfolio-lab/project-catalog";
import { LabGrantEditor } from "../../../components/lab-grant-editor";
import styles from "../../../components/lab-auth.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Manage portfolio access", robots: { index: false, follow: false } };

export default async function LabAdminPage({ searchParams }: { searchParams: Promise<{ after?: string }> }) {
  if (!isLabEnabled()) notFound();
  const claims = await currentLabSession().catch(() => null);
  if (!claims) redirect("/lab/login");
  if (claims.uid !== getOwnerUid()) notFound();
  const { after } = await searchParams;
  if (after && (after.length > 128 || after.includes("/") || after === "." || after === "..")) notFound();
  const result = await listLabUsers(after).catch(() => null);

  return (
    <section className={`${styles.panel} ${styles.ownerPanel}`}>
      <header className={styles.header}>
        <h1>Manage portfolio access</h1>
        <p>View allows reading. Test allows demo changes. Admin also manages project settings.</p>
        <Link href="/lab" className={styles.textAction}>Back to your account</Link>
      </header>
      {!result && <p className={styles.notice} role="alert">Account access is temporarily unavailable. Reload to retry.</p>}
      {result?.users.length === 0 && <p className={styles.hint}>Registered accounts will appear here.</p>}
      {result?.users.map((user) => (
        <section key={user.uid} className={styles.userCard}>
          <h2 className={styles.providerLabel}>{user.email ?? "Account without an email address"}</h2>
          <p className={styles.accountId}>Account ID {user.uid}</p>
          {user.disabled && <p className={styles.hint}>Account disabled</p>}
          {user.grants.map((grant) => (
            <LabGrantEditor key={grant.projectId} uid={user.uid} projectId={grant.projectId}
              title={labProjects.find((project) => project.id === grant.projectId)!.title}
              role={grant.role} revision={grant.revision} disabled={user.disabled || user.uid === claims.uid} />
          ))}
        </section>
      ))}
      {result?.next && <Link className={styles.secondaryButton} href={`/lab/admin?after=${encodeURIComponent(result.next)}`}>Next accounts</Link>}
      {after && <Link className={styles.textAction} href="/lab/admin">First page</Link>}
    </section>
  );
}
