import styles from "./workforce-scaffold.module.css";

/** Inert preview component; never mount before shared project-grant checks exist. */
export function WorkforceScaffold() {
  return (
    <section className={styles.root} aria-labelledby="workforce-scaffold-title">
      <p className={styles.eyebrow}>Synthetic demonstration / not an official system</p>
      <h1 id="workforce-scaffold-title">Workforce &amp; Recruitment Intelligence</h1>
      <p>
        Project foundation only. Access-controlled analytical features are not yet available.
      </p>
    </section>
  );
}
