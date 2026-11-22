import Image from "next/image";
import Link from "next/link";
import { projectOverviews } from "../content/portfolio";
import type { LabProject } from "../lib/portfolio-lab/project-catalog";
import type { ProjectRole } from "../lib/portfolio-lab/project-grants";
import styles from "../app/portfolio/page.module.css";

type ProjectCard = LabProject & { role?: ProjectRole | null };
const descriptions: Record<string, string> = {
  fleet_hub: "Log vehicle defects, track repairs and see which vehicles are ready to return to service. Import your own vehicle records and export fleet data to Excel.",
  workforce_intelligence: "Explore staffing, recruitment and staff feedback. Start with synthetic data, or import, process and export your own datasets.",
};

export function ProjectCards({ projects, detailed = false }: { projects: readonly ProjectCard[]; detailed?: boolean }) {
  if (detailed) {
    return <ul className={styles.caseStudies}>
      {projects.map((project) => <li key={project.id}><ProjectCaseStudy project={project} /></li>)}
    </ul>;
  }

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

function ProjectCaseStudy({ project }: { project: ProjectCard }) {
  const overview = projectOverviews[project.id];
  return <article className={styles.caseStudy} aria-labelledby={`${project.id}-title`}>
    <div className={styles.caseHeader}>
      <span className={styles.category}>{project.category}</span>
      <span className={styles.accessBadge}>Access by permission</span>
    </div>
    <h2 id={`${project.id}-title`}>{project.title}</h2>
    <p className={styles.focus}>{overview?.focus || project.summary}</p>
    <div className={styles.caseBody}>
      <div>
        {overview && <figure className={styles.preview}>
          <a className={styles.previewLink} href={overview.preview.src} target="_blank" rel="noopener noreferrer"
            aria-label={`View ${project.title} screenshot (opens in a new tab)`}>
            <Image className={styles.previewImage} src={overview.preview.src} alt={overview.preview.alt}
              width={1440} height={900} sizes="(max-width: 760px) calc(100vw - 5rem), (max-width: 1100px) 45vw, 480px" />
          </a>
          <figcaption>{overview.preview.caption} · Select to enlarge</figcaption>
        </figure>}
        {overview && <h3>The challenge</h3>}
        <p>{overview?.challenge || project.summary}</p>
      </div>
      {overview && <div>
        <h3>The approach</h3>
        <p>{overview.approach}</p>
        <div className={styles.explore}>
          <h3>Inside the demo</h3>
          <ul>{overview.highlights.map((highlight) => <li key={highlight}>{highlight}</li>)}</ul>
        </div>
      </div>}
    </div>
    <ul className={styles.technologies} aria-label={`${project.title} technologies`}>
      {project.technologies.map((technology) => <li key={technology}>{technology}</li>)}
    </ul>
    <div className={styles.caseFooter}>
      <span>Concept prototype · Synthetic data, with support for importing, processing and exporting your own datasets.</span>
      <Link className={styles.demoLink} href={project.path} aria-label={`Open ${project.title} demo`}>
        Open demo
      </Link>
    </div>
  </article>;
}
