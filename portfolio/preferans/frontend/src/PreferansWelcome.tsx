import copy from "./content.ru.json";
import styles from "./preferans-welcome.module.css";

/** Project-local placeholder. Real game actions require reviewed backend security. */
export function PreferansWelcome() {
  return (
    <main className={styles.root}>
      <section className={styles.card} aria-labelledby="preferans-title">
        <p className={styles.eyebrow}>{copy.status}</p>
        <h1 id="preferans-title" className={styles.title}>{copy.title}</h1>
        <p className={styles.description}>{copy.message}</p>
        <p className={styles.notice}>{copy.privacy}</p>
      </section>
    </main>
  );
}
