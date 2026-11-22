import Link from "next/link";
import styles from "./demo-site-bar.module.css";

export function DemoSiteBar() {
  return <nav className={styles.bar} aria-label="Demo navigation">
    <Link className={styles.backLink} href="/portfolio">← Back to portfolio</Link>
    <span className={styles.disclosure}>Demo v1.0 · Synthetic data only</span>
  </nav>;
}
