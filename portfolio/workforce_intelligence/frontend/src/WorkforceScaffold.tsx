"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type MouseEvent } from "react";
import {
  WORKFORCE_DEFAULT_MODE,
  WORKFORCE_MODES,
  modeFromSearch,
  workforceModeHref,
  type WorkforceMode,
} from "./mode-state";
import styles from "./workforce-scaffold.module.css";

type Connection = "checking" | "ready" | "unauthenticated" | "denied" | "disabled" | "unavailable";
type AppTheme = "dark" | "light";

const subscribeToLocation = (notify: () => void) => {
  window.addEventListener("popstate", notify);
  return () => window.removeEventListener("popstate", notify);
};
const getLocationMode = () => modeFromSearch(window.location.search);
const getServerMode = (): WorkforceMode => WORKFORCE_DEFAULT_MODE;

let storageFallbackTheme: AppTheme = "dark";
const subscribeToTheme = (notify: () => void) => {
  window.addEventListener("storage", notify);
  window.addEventListener("workforce-theme-change", notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener("workforce-theme-change", notify);
  };
};
const getBrowserTheme = (): AppTheme => {
  try { return window.localStorage.getItem("workforce-theme") === "light" ? "light" : "dark"; }
  catch { return storageFallbackTheme; }
};
const getServerTheme = (): AppTheme => "dark";

type Section = {
  label: string;
  short: string;
  description: string;
  planned: readonly string[];
};

const sections: Record<WorkforceMode, Section> = {
  "workforce-intelligence": {
    label: "Workforce Intelligence",
    short: "Analysis & KPIs",
    description: "An evidence-led view of establishment, recruitment, retention and workforce trends.",
    planned: ["Executive KPI dashboard", "Vacancy and establishment gap", "Recruitment conversion funnel"],
  },
  "workforce-management": {
    label: "Workforce Management",
    short: "Source records",
    description: "Controlled changes to synthetic employment, contracts, assignments and recruitment events.",
    planned: ["Employees and assignments", "Vacancy and applicant lifecycle", "Audited source changes"],
  },
  "people-voice": {
    label: "People Voice",
    short: "Survey evidence",
    description: "Synthetic employee feedback, evidence-linked findings and mandatory human review.",
    planned: ["Synthetic surveys", "Evidence-linked findings", "Review and publication"],
  },
  "data-architecture": {
    label: "Data Architecture",
    short: "Governance & lineage",
    description: "A transparent explanation of data ownership, transformations and metric definitions.",
    planned: ["Bronze / Silver / Gold", "Data contracts and lineage", "Quality and metric catalogue"],
  },
};

const statusMessage: Record<Connection, string> = {
  checking: "Verifying protected API...",
  ready: "Protected API verified",
  unauthenticated: "Session expired",
  denied: "Project access revoked",
  disabled: "Workspace unavailable",
  unavailable: "Backend connection unavailable",
};

/** Browser navigation is local; the protected Next.js entry remains server-authorized. */
export function WorkforceScaffold({ previewMode = false }: { previewMode?: boolean }) {
  const mode = useSyncExternalStore(subscribeToLocation, getLocationMode, getServerMode);
  const theme = useSyncExternalStore(subscribeToTheme, getBrowserTheme, getServerTheme);
  const [connection, setConnection] = useState<Connection>("checking");
  const pending = useRef<AbortController | null>(null);

  const verifyBackend = useCallback(async () => {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    try {
      const response = await fetch("/portfolio/workforce-intelligence/api/status", {
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (response.status === 401) { setConnection("unauthenticated"); return; }
      if (response.status === 403) { setConnection("denied"); return; }
      if (response.status === 404) { setConnection("disabled"); return; }
      if (!response.ok) { setConnection("unavailable"); return; }
      const payload: unknown = await response.json();
      if (controller.signal.aborted) return;
      const valid = payload !== null && typeof payload === "object" &&
        "service" in payload && payload.service === "workforce" &&
        "available" in payload && payload.available === true;
      setConnection(valid ? "ready" : "unavailable");
    } catch {
      if (!controller.signal.aborted) setConnection("unavailable");
    } finally {
      if (pending.current === controller) pending.current = null;
    }
  }, []);

  useEffect(() => {
    // Local UI preview is completely offline: no BFF, Firebase or FastAPI requests.
    if (previewMode) return;
    void verifyBackend();
    return () => pending.current?.abort();
  }, [previewMode, verifyBackend]);

  const navigate = (event: MouseEvent<HTMLAnchorElement>, destination: WorkforceMode) => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey ||
        event.altKey || event.shiftKey) return;
    event.preventDefault();
    const href = workforceModeHref(destination, previewMode);
    if (window.location.pathname + window.location.search !== href) {
      window.history.pushState(null, "", href);
    }
    window.dispatchEvent(new PopStateEvent("popstate"));
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  const switchTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    storageFallbackTheme = next;
    try { window.localStorage.setItem("workforce-theme", next); } catch { /* optional */ }
    window.dispatchEvent(new Event("workforce-theme-change"));
  };

  const locked = !previewMode && (connection === "unauthenticated" || connection === "denied" || connection === "disabled");
  const selected = sections[mode];

  return (
    <section className={styles.root} data-theme={theme} aria-label="Workforce Intelligence demo">
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">WI</span>
          <div>
            <p className={styles.overline}>PORTFOLIO LAB / SYNTHETIC DATA</p>
            <p className={styles.brandName}>Workforce Intelligence</p>
          </div>
        </div>
        <div className={styles.headerActions}>
          <span className={styles.previewLabel}>PREVIEW</span>
          <button type="button" className={styles.themeButton} onClick={switchTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {theme === "dark" ? "Light theme" : "Dark theme"}
          </button>
        </div>
      </header>

      <div className={styles.body}>
        <aside className={styles.sidebar}>
          <p className={styles.sidebarHeading}>WORKSPACES</p>
          <nav aria-label="Workforce sections" className={styles.navigation}>
            {WORKFORCE_MODES.map((id, index) => (
              <a key={id} href={workforceModeHref(id, previewMode)}
                className={`${styles.navItem} ${mode === id ? styles.navItemActive : ""}`}
                aria-current={mode === id ? "page" : undefined}
                onClick={(event: MouseEvent<HTMLAnchorElement>) => navigate(event, id)}>
                <span className={styles.navNumber} aria-hidden="true">0{index + 1}</span>
                <span className={styles.navCopy}>
                  <strong>{sections[id].label}</strong>
                  <small>{sections[id].short}</small>
                </span>
              </a>
            ))}
          </nav>
          <div className={styles.sidebarFoot}>
            {previewMode ? (
              <span className={styles.localPreviewNote}>Local-only UI preview</span>
            ) : (
              <a href="/portfolio">Back to Portfolio Lab</a>
            )}
            <p>Demo v1.0 · Not an official SCAS system</p>
          </div>
        </aside>

        <div className={styles.content}>
          {previewMode ? (
            <div className={styles.statusBar} role="status">
              <span className={`${styles.statusDot} ${styles.statusDotReady}`} aria-hidden="true" />
              <span>Local UI preview — no Firebase or API calls</span>
            </div>
          ) : (
            <div className={styles.statusBar} role="status" aria-live="polite">
              <span className={`${styles.statusDot} ${connection === "ready" ? styles.statusDotReady : ""}`} aria-hidden="true" />
              <span>{statusMessage[connection]}</span>
              {connection !== "checking" && connection !== "ready" &&
                <button type="button" onClick={() => { setConnection("checking"); void verifyBackend(); }} className={styles.retryButton}>
                  Retry check
                </button>}
            </div>
          )}

          {locked ? (
            <div className={styles.blocked}>
              <h1>Workspace access unavailable</h1>
              <p>{connection === "unauthenticated" ? "Your sign-in session has expired." :
                connection === "denied" ? "Your Workforce project membership is no longer active." :
                  "This preview is currently disabled."}</p>
              <a href="/lab/login">Return to sign in</a>
            </div>
          ) : (
            <section className={styles.mainContent} id="workforce-panel" aria-labelledby="workforce-heading">
              <p className={styles.overline}>WORKFORCE / {mode.replaceAll("-", " ").toUpperCase()}</p>
              <h1 id="workforce-heading">{selected.label}</h1>
              <p className={styles.intro}>{selected.description}</p>
              <div className={styles.notice}>
                <strong>Implementation preview</strong>
                <span>{previewMode
                  ? "Visual inspection only: no credentials, backend connection or business operations. Data workflows are not yet implemented."
                  : "Navigation and access infrastructure are implemented. Data workflows and live metrics are scheduled for later releases."}</span>
              </div>
              <h2 className={styles.sectionTitle}>Planned capabilities</h2>
              <div className={styles.cards}>
                {selected.planned.map((feature, index) => (
                  <article className={styles.card} key={feature}>
                    <span className={styles.cardNumber}>0{index + 1}</span>
                    <h3>{feature}</h3>
                    <p>Not yet implemented</p>
                  </article>
                ))}
              </div>
              <div className={styles.emptyState}>
                <span className={styles.emptyGlyph} aria-hidden="true">◇</span>
                <div>
                  <h2>No analytical data available yet</h2>
                  <p>The separate Workforce SQLite data model and governed KPIs will be introduced in the next development phase. No placeholder figures are presented as real results.</p>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
      <footer className={styles.footer}>
        Demo v1.0 | Prepared for an SCAS interview | Synthetic data only | Not an official SCAS system
      </footer>
    </section>
  );
}
