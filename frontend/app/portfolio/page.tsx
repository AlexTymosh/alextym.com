import type { Metadata } from "next";
import Link from "next/link";
import { ProjectCards } from "../../components/project-cards";
import { publicProjects } from "../../lib/portfolio-lab/project-catalog";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Portfolio",
  description: "Working concepts for operational workflows, system integration and AI-assisted workforce analytics.",
  alternates: { canonical: "/portfolio" },
};

export default function PortfolioCataloguePage() {
  return (
    <div className={styles.portfolio}>
      <header className={styles.intro}>
        <p className={styles.eyebrow}>Working concepts</p>
        <h1>Portfolio</h1>
        <p className={styles.lead}>Business problems, explored through working software.</p>
        <p>A quick look at each project&apos;s purpose, approach and workflows.
          These concept prototypes use synthetic data.</p>
      </header>
      <aside className={styles.accessNotice} aria-label="Demo access">
        <span>Interactive demos require sign-in and permission for each project.</span>
        <Link href="/sign-in">Sign in</Link>
        <Link href="/contact">Request access</Link>
      </aside>
      <ProjectCards projects={publicProjects} detailed />
    </div>
  );
}
