import type { Metadata } from "next";
import { ProjectCards } from "../../components/project-cards";
import { labProjects } from "../../lib/portfolio-lab/project-catalog";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Portfolio demonstrations",
  robots: { index: false, follow: false },
};

export default function PortfolioCataloguePage() {
  return (
    <main className={styles.portfolio}>
      <h1>Portfolio demonstrations</h1>
      <p>Two interactive projects with synthetic data.</p>
      <ProjectCards projects={labProjects} />
    </main>
  );
}
