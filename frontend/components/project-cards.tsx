import Image from "next/image";
import Link from "next/link";
import type { ProjectRole } from "../lib/portfolio-lab/project-grants";
import styles from "../app/portfolio/page.module.css";

type ProjectCard = { id: string; title: string; summary: string; path: string; role?: ProjectRole | null };
const descriptions: Record<string, string> = {
  fleet_hub: "Log vehicle defects, track repairs and see which vehicles are ready to return to service.",
  workforce_intelligence: "Explore staffing, recruitment and staff feedback in a synthetic workforce dashboard.",
};

export function ProjectCards({ projects }: { projects: readonly ProjectCard[] }) {
  return <ul className={styles.projects}>
    {projects.map((project) => <li key={project.id}>
      <Link className={styles.card} href={project.path}>
        {project.id === "workforce_intelligence"
          ? <Image className={styles.logo} src="/workforce-simulation-logo.png" alt="" width={64} height={64} />
          : <span className={styles.logo} aria-hidden="true">
            <svg viewBox="0 0 32 32" width="36" height="36" fill="none" stroke="currentColor"
              strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9h16v13H3zm16 5h5l5 5v3H19M3 25h3m8 0h7m6 0h2" />
              <circle cx="10" cy="24" r="3" fill="currentColor" /><circle cx="24" cy="24" r="3" fill="currentColor" />
            </svg>
          </span>}
        <h2>{project.title}</h2>
        <p>{descriptions[project.id] || project.summary}</p>
        {project.role && <span className={styles.access}>{project.role} access</span>}
        <span className={styles.cta}>Open demo <span aria-hidden="true">→</span></span>
      </Link>
    </li>)}
  </ul>;
}
