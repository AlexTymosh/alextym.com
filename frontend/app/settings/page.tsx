import Link from "next/link";
import { redirect } from "next/navigation";
import { ProjectCards } from "../../components/project-cards";
import { labProjects } from "../../lib/portfolio-lab/project-catalog";
import { currentLabSession, labProjectRole } from "../../lib/portfolio-lab/project-access-server";
import authStyles from "../../components/lab-auth.module.css";
import styles from "../../components/settings.module.css";

export default async function AvailableProjectsPage() {
  const session = await currentLabSession();
  if (!session) redirect("/sign-in");
  const projects = await Promise.all(labProjects.map(async (project) => ({
    ...project, role: await labProjectRole(session.uid, project.id),
  })));
  const available = projects.filter((project) => project.role);
  return <section>
    <h2>Available projects</h2>
    <p className={styles.description}>You have access to the following projects. Your access level is shown on each card.</p>
    {available.length > 0 ? <ProjectCards projects={available} />
      : <p className={authStyles.notice} role="status">No access has been assigned to your account.</p>}
    <Link className={authStyles.textAction} href="/settings">Refresh access</Link>
  </section>;
}
