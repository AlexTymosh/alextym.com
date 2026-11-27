import { createTranslator, DEFAULT_LOCALE } from "./i18n/messages";
import styles from "./foundation.module.css";

export function SamePlaceFoundation() {
  const t = createTranslator(DEFAULT_LOCALE, { strict: process.env.NODE_ENV !== "production" });
  return (
    <section className={styles.foundation} lang={DEFAULT_LOCALE} aria-labelledby="sameplace-title">
      <p className={styles.eyebrow}>{t("foundation.stage")}</p>
      <h1 id="sameplace-title">SamePlace</h1>
      <p className={styles.motto}>{t("foundation.motto")}</p>
      <p>{t("foundation.description")}</p>
      <p className={styles.notice}>{t("foundation.notice")}</p>
    </section>
  );
}
