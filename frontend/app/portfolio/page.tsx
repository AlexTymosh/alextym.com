import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
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
      <ul className={styles.projects}>
        <li>
          <Link className={styles.card} href="/fleet-vor-hub">
            <span className={styles.logo} aria-hidden="true">
              <svg viewBox="0 0 32 32" width="36" height="36" fill="none" stroke="currentColor"
                strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 9h16v13H3zm16 5h5l5 5v3H19M3 25h3m8 0h7m6 0h2"/>
                <circle cx="10" cy="24" r="3" fill="currentColor"/><circle cx="24" cy="24" r="3" fill="currentColor"/>
              </svg>
            </span>
            <h2>Fleet VOR Hub</h2>
            <p>Log vehicle defects, track repairs and see which vehicles are ready to return to service.</p>
            <span className={styles.cta}>Open demo <span aria-hidden="true">→</span></span>
          </Link>
        </li>
        <li>
          <Link className={styles.card} href="/portfolio/workforce-intelligence">
            <Image className={styles.logo} src="/workforce-simulation-logo.png" alt="" width={64} height={64}/>
            <h2>Workforce &amp; Recruitment Intelligence</h2>
            <p>Explore staffing, recruitment and staff feedback in a synthetic workforce dashboard.</p>
            <span className={styles.cta}>Open demo <span aria-hidden="true">→</span></span>
          </Link>
        </li>
      </ul>
    </main>
  );
}
