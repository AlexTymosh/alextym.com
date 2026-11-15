"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type MouseEvent } from "react";
import { DEFAULT_FILTERS, loadWorkspace, sameGeneration, WorkforceApiError,
  type DatasetVersion, type Filters, type Workspace } from "./data-api";
import { ExecutiveDashboard } from "./ExecutiveDashboard";
import { displayRefresh } from "./format";
import { WORKFORCE_DEFAULT_MODE, WORKFORCE_MODES, modeFromSearch, workforceModeHref,
  type WorkforceMode } from "./mode-state";
import { WorkforceManagement } from "./WorkforceManagement";
import styles from "./workforce-scaffold.module.css";

type AppTheme = "dark" | "light";
type ReadResult = { key: string; data: Workspace } | { key: string; error: WorkforceApiError };

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

const sections: Record<WorkforceMode, {
  label: string; description: string; outline: [id: string, name: string][]; planned: string;
}> = {
  "workforce-intelligence": {
    label: "Workforce Intelligence", description: "Recruitment performance and establishment at a glance.",
    outline: [["executive", "Recruitment overview"], ["vacancies", "Vacancy lifecycle"], ["funnel", "Candidate funnel"]],
    planned: "Attraction, workforce outcomes, equality and forecasting.",
  },
  "workforce-management": {
    label: "Workforce Management", description: "Review synthetic source records and record a contract change.",
    outline: [["directory", "People directory"], ["contracts", "Contracts & FTE"]],
    planned: "Full employment and recruitment lifecycle, Excel, learning and PDR.",
  },
  "people-voice": {
    label: "People Voice", description: "Evidence from synthetic staff surveys.", outline: [],
    planned: "Survey builder, generated responses and evidence review.",
  },
  "data-architecture": {
    label: "Data Architecture", description: "Data ownership, quality and lineage.", outline: [],
    planned: "Lineage explorer, source registry and quality dashboards.",
  },
};

export function WorkforceScaffold({ previewMode = false }: { previewMode?: boolean }) {
  const mode = useSyncExternalStore(subscribeToLocation, getLocationMode, getServerMode);
  const theme = useSyncExternalStore(subscribeToTheme, getBrowserTheme, getServerTheme);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [read, setRead] = useState<ReadResult | null>(null);
  const [notice, setNotice] = useState("");
  const priorGeneration = useRef<DatasetVersion | null>(null);
  const { start, end, vacancyId } = filters;
  const readKey = `${mode}:${start}:${end}:${vacancyId}:${offset}:${reload}`;
  const active = read?.key === readKey ? read : null;
  const workspace = active && "data" in active ? active.data : null;
  const error = active && "error" in active ? active.error : null;
  const dataset = workspace?.dataset;
  const selected = sections[mode];
  const refresh = () => setReload((version) => version + 1);

  useEffect(() => {
    if (previewMode) return;
    const controller = new AbortController();
    void loadWorkspace(mode, { start, end, vacancyId }, offset, controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      if (priorGeneration.current && !sameGeneration(priorGeneration.current, data.dataset)) {
        setNotice("The demo dataset was reset or regenerated. This view has been refreshed.");
      }
      priorGeneration.current = data.dataset;
      setRead({ key: readKey, data });
    }).catch((failure: unknown) => {
      if (controller.signal.aborted) return;
      setRead({ key: readKey, error: failure instanceof WorkforceApiError ? failure :
        new WorkforceApiError(503, "The data service is unavailable. Retry shortly.") });
    });
    return () => controller.abort();
  }, [previewMode, mode, start, end, vacancyId, offset, readKey]);

  useEffect(() => {
    if (previewMode) return;
    const checkOnReturn = () => {
      if (document.visibilityState === "visible") setReload((version) => version + 1);
    };
    document.addEventListener("visibilitychange", checkOnReturn);
    return () => document.removeEventListener("visibilitychange", checkOnReturn);
  }, [previewMode]);

  const navigate = (event: MouseEvent<HTMLAnchorElement>, destination: WorkforceMode) => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey ||
        event.altKey || event.shiftKey) return;
    event.preventDefault();
    const href = workforceModeHref(destination, previewMode);
    if (window.location.pathname + window.location.search + window.location.hash !== href) {
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

  const restricted = Boolean(error && [401, 403, 404].includes(error.status));

  return (
    <section className={styles.root} data-theme={theme} aria-label="Workforce Intelligence demo">
      <p className={styles.disclosure}>Demo v1.0 | Prepared for an SCAS interview | Synthetic data only | Not an official SCAS system</p>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">WI</span>
          <div><p className={styles.brandName}>Workforce & Recruitment Intelligence</p>
            <p className={styles.brandContext}>Portfolio Lab</p></div>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.secondaryButton} onClick={switchTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {theme === "dark" ? "Light theme" : "Dark theme"}
          </button>
          {!previewMode && !restricted ? <details className={styles.account}>
            <summary>Account</summary><div><strong>Member</strong><a href="/lab">Manage sign-in</a></div>
          </details> : null}
        </div>
      </header>
      <nav aria-label="Workforce sections" className={styles.navigation}>
        {WORKFORCE_MODES.map((id) => (
          <a key={id} href={workforceModeHref(id, previewMode)} aria-current={mode === id ? "page" : undefined}
            className={`${styles.navItem} ${mode === id ? styles.navItemActive : ""}`}
            onClick={(event) => navigate(event, id)}>{sections[id].label}</a>
        ))}
      </nav>

      <div className={styles.body}>
        <aside className={styles.sidebar}>
          {workspace && selected.outline.length ? <nav aria-label={`${selected.label} outline`}>
            {selected.outline.map(([id, name]) => <a key={id} href={`#${id}`}>{name}</a>)}
          </nav> : null}
          <div className={styles.sidebarFoot}>{previewMode ? <span>Local-only UI preview</span> :
            <a href="/portfolio">Back to Portfolio Lab</a>}</div>
        </aside>
        <div className={styles.content}>
          <div className={styles.statusBar} role="status">
            <span className={`${styles.statusDot} ${dataset ? styles.statusDotReady : ""}`} aria-hidden="true" />
            {previewMode ? <span>Local UI preview — no Firebase or API calls</span> : dataset ? (
              <><span>Dataset {dataset.dataset_generation} · Revision {dataset.revision}</span>
                <span>Refreshed <time dateTime={dataset.refreshed_at}>{displayRefresh(dataset.refreshed_at)} UK</time></span>
                <button type="button" className={styles.linkButton} onClick={refresh}>Refresh data</button></>
            ) : <span>{error ? "Data unavailable" : "Loading protected data…"}</span>}
          </div>

          <section className={styles.mainContent} id="workforce-panel" aria-labelledby="workforce-heading">
            <div className={styles.pageHeading}><h1 id="workforce-heading">{selected.label}</h1>
              <p>{selected.description}</p></div>
            {!restricted && notice ? <p className={styles.notice} role="status">{notice}</p> : null}
            {previewMode ? <p className={styles.message}>Sign in to the protected app to view and change the synthetic dataset.</p> : null}
            {error ? <div className={styles.panel} role="alert">
              <h2>{restricted ? "Workspace access unavailable" : "Unable to load this view"}</h2>
              <p>{error.status === 401 ? "Your sign-in session has expired." : error.status === 403 ?
                "Your Workforce project membership is no longer active." : error.status === 404 ?
                  "This workspace is currently disabled." : error.message}</p>
              {error.status === 401 ? <a href="/lab/login">Return to sign in</a> :
                <button type="button" className={styles.secondaryButton}
                  onClick={() => { if (error.status === 422) setFilters(DEFAULT_FILTERS); refresh(); }}>
                  {error.status === 422 ? "Restore default dates" : "Retry"}
                </button>}
            </div> : null}
            {workspace?.kind === "workforce-intelligence" ? <ExecutiveDashboard
              dashboard={workspace.dashboard} filters={filters} onFilters={setFilters} /> : null}
            {workspace?.kind === "workforce-management" ? <WorkforceManagement directory={workspace.directory}
              offset={offset} onPage={setOffset} onSaved={(message) => { setNotice(message); refresh(); }}
              onConflict={() => { setNotice("The dataset or contract changed. Choose the employee again after refresh."); refresh(); }}
              onError={(failure) => setRead({ key: readKey, error: failure })} /> : null}
            {workspace && workspace.kind !== "workforce-management" ? <details className={styles.planned}>
              <summary>Planned capabilities</summary><p>{selected.planned}</p>
            </details> : null}
          </section>
        </div>
      </div>
    </section>
  );
}
