import type { Metadata } from "next";
import { PortfolioAccessNotice } from "../../components/portfolio-access-notice";
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
          These concept prototypes use synthetic data and support importing, processing
          and exporting your own datasets.</p>
      </header>
      <PortfolioAccessNotice />
      <ProjectCards projects={publicProjects} detailed />
    </div>
  );
}
