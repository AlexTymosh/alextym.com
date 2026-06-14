import type { Metadata } from "next";

import { DocumentSwitcher, type CaseStudyDocument } from "./DocumentSwitcher";
import styles from "./page.module.css";

const documents: CaseStudyDocument[] = [
  {
    id: "report",
    label: "Report",
    eyebrow: "Report",
    title: "Visual report",
    description: "A short visual summary of the analysis and key findings.",
    path: "/projects/netflix-data-visualisation-case-study.pdf",
  },
  {
    id: "technical-notebook",
    label: "Technical notebook",
    eyebrow: "Technical notebook",
    title: "Technical notebook",
    description: "Supporting document with data preparation, exploratory analysis, code and checks.",
    path: "/projects/netflix-technical-notebook.pdf",
  },
];

const tools = ["Python", "Pandas", "Matplotlib", "Seaborn", "Plotly", "GeoPandas"];

const highlights = [
  "Prepared a public Netflix catalogue dataset for exploratory analysis.",
  "Analysed catalogue growth, content mix, ratings, genres, countries, duration and seasonal patterns.",
  "Created visual summaries to support analytical storytelling.",
  "Separated the work into a concise report and a supporting technical notebook.",
];

export const metadata: Metadata = {
  title: "Netflix Catalogue Analysis",
  description:
    "Data visualisation case study using Python, Pandas, Matplotlib, Seaborn, Plotly and GeoPandas.",
  robots: {
    index: false,
    follow: false,
  },
  alternates: {
    canonical: "/case-studies/netflix-catalogue-analysis",
  },
  openGraph: {
    title: "Netflix Catalogue Analysis",
    description:
      "A data visualisation portfolio case study focused on data preparation, exploratory analysis and analytical storytelling.",
    type: "article",
    url: "/case-studies/netflix-catalogue-analysis",
  },
};

export default function NetflixCatalogueAnalysisPage() {
  return (
    <section className={styles.caseStudy} aria-labelledby="case-study-title">
      <div className={styles.hero}>
        <div className={styles.heroHeader}>
          <div className={styles.heroCopy}>
            <p className="eyebrow">Data visualisation case study</p>
            <h1 id="case-study-title">Netflix Catalogue Analysis</h1>
            <p>
              A portfolio case study based on a public Netflix catalogue dataset. It demonstrates data
              preparation, exploratory analysis, chart selection and concise presentation of findings.
            </p>
            <p className={styles.projectMeta}>
              Originally completed during the Cambridge Spark Data Analytics bootcamp final hackathon and
              later refined as a portfolio case study. The report gives a short visual summary; the technical
              notebook shows the supporting workflow and code.
            </p>
          </div>
        </div>
      </div>

      <div className={styles.summaryGrid}>
        <article className={styles.panel}>
          <p className="eyebrow">Scope</p>
          <h2>What the case study shows</h2>
          <ul>
            {highlights.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className={styles.panel}>
          <p className="eyebrow">Relevance</p>
          <h2>Why it is included</h2>
          <p>
            This is supporting portfolio evidence for data analysis, visualisation and communication skills. It is
            a bootcamp case study, not a production BI dashboard.
          </p>
        </article>

        <article className={styles.panel}>
          <p className="eyebrow">Tools</p>
          <h2>Technical stack</h2>
          <div className={styles.toolList} aria-label="Tools used in the project">
            {tools.map((tool) => (
              <span key={tool}>{tool}</span>
            ))}
          </div>
        </article>
      </div>

      <DocumentSwitcher documents={documents} />
    </section>
  );
}
