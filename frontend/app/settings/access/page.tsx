import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { currentLabSession } from "../../../lib/portfolio-lab/project-access-server";
import { getOwnerUid, isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { listLabUsers } from "../../../lib/portfolio-lab/owner-access-server";
import { labProjects } from "../../../lib/portfolio-lab/project-catalog";
import { LabGrantEditor } from "../../../components/lab-grant-editor";
import { PreferansAliasEditor } from "../../../components/preferans-alias-editor";
import styles from "../../../components/lab-auth.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Access management", robots: { index: false, follow: false } };

export default async function LabAdminPage({ searchParams }: { searchParams: Promise<{ after?: string }> }) {
  if (!isLabEnabled()) notFound();
  const claims = await currentLabSession().catch(() => null);
  if (!claims) redirect("/sign-in");
  if (claims.uid !== getOwnerUid()) notFound();
  const { after } = await searchParams;
  if (after && (after.length > 128 || after.includes("/") || after === "." || after === "..")) notFound();
  const result = await listLabUsers(after).catch(() => null);

  return (
    <section className={styles.embeddedPanel}>
      <header className={styles.header}>
        <h2>Access management</h2>
        <p>View allows reading. Test allows changes. Admin also manages settings.</p>
      </header>
      {!result && <p className={styles.notice} role="alert">Account access is temporarily unavailable. Reload to retry.</p>}
      {result?.users.length === 0 && <p className={styles.hint}>Registered accounts will appear here.</p>}
      {result && result.users.length > 0 && (
        <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="User access table">
          <table className={styles.accessTable}>
            <caption className={styles.srOnly}>Access by user and project</caption>
            <thead>
              <tr>
                <th scope="col">User</th>
                <th scope="col">Linked accounts</th>
                <th scope="col">Preferans nickname</th>
                {labProjects.map((project) => <th key={project.id} scope="col">{project.title}</th>)}
              </tr>
            </thead>
            <tbody>
              {result.users.map((user) => (
                <tr key={user.uid} data-user-id={user.uid}>
                  <th scope="row">
                    <p className={styles.providerLabel}>{user.email ?? "User without an email address"}</p>
                    <p className={styles.accountId}>ID {user.uid}</p>
                    {user.disabled && <p className={styles.hint}>Disabled</p>}
                  </th>
                  <td>
                    <ul className={styles.linkedAccounts}>
                      {user.linkedAccounts.map((account) => (
                        <li key={account.provider}>
                          <span className={styles.methodName}>{account.name}</span>
                          {account.email && <span className={styles.methodEmail}>{account.email}</span>}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td><PreferansAliasEditor uid={user.uid} initial={user.alias} disabled={user.disabled}/></td>
                  {labProjects.map((project) => {
                    const grant = user.grants.find((entry) => entry.projectId === project.id)!;
                    return (
                      <td key={project.id}>
                        <LabGrantEditor uid={user.uid} projectId={project.id}
                          title={`${project.title} access for ${user.email ?? user.uid}`}
                          role={grant.role} revision={grant.revision} disabled={user.disabled || user.uid === claims.uid} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {result?.next && <Link className={styles.secondaryButton} href={`/settings/access?after=${encodeURIComponent(result.next)}`}>Next accounts</Link>}
      {after && <Link className={styles.textAction} href="/settings/access">First page</Link>}
    </section>
  );
}
