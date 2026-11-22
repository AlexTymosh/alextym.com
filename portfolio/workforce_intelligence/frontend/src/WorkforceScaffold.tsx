"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type MouseEvent } from "react";
import { DataArchitecture } from "./DataArchitecture";
import { DEFAULT_FILTERS, loadWorkspace, sameGeneration, WorkforceApiError,
  type DatasetVersion, type Filters, type Workspace } from "./data-api";
import { ExecutiveDashboard } from "./ExecutiveDashboard";
import { ForecastPanel } from "./ForecastPanel";
import { displayRefresh } from "./format";
import { InsightPilot } from "./InsightPilot";
import { InterviewGuide } from "./InterviewGuide";
import { guideHref, readGuide, type GuideName } from "./interview";
import { WORKFORCE_MODES, WORKFORCE_NAVIGATION, modeFromSearch, screenFromLocation, workforceModeHref,
  type WorkforceScreen } from "./mode-state";
import { PeopleVoice } from "./PeopleVoice";
import { ResetDemo } from "./ResetDemo";
import { ScenarioPanel } from "./ScenarioPanel";
import { WorkforceManagement } from "./WorkforceManagement";
import styles from "./workforce-scaffold.module.css";

type AppTheme = "dark" | "light";
type ReadResult = { key: string; data: Workspace } | { key: string; error: WorkforceApiError };

const subscribeToLocation = (notify: () => void) => {
  window.addEventListener("popstate", notify);
  window.addEventListener("hashchange", notify);
  return () => {
    window.removeEventListener("popstate", notify);
    window.removeEventListener("hashchange", notify);
  };
};
const getBrowserLocation = () => window.location.search + window.location.hash;
const getServerLocation = () => "";

function moveTo(href: string) {
  if (window.location.pathname + window.location.search + window.location.hash !== href) {
    window.history.pushState(null, "", href);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

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

export function WorkforceScaffold({ previewMode = false, onSignOut }: { previewMode?: boolean; onSignOut?: () => void }) {
  const location = useSyncExternalStore(subscribeToLocation, getBrowserLocation, getServerLocation);
  const [search, fragment] = location.split("#", 2);
  const mode = modeFromSearch(search);
  const guide = previewMode ? null : readGuide(search);
  const screen = guide && !new URLSearchParams(search).has("section")
    ? guide.step.target : screenFromLocation(mode, search, fragment ? `#${fragment}` : "");
  const theme = useSyncExternalStore(subscribeToTheme, getBrowserTheme, getServerTheme);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [read, setRead] = useState<ReadResult | null>(null);
  const [notice, setNotice] = useState("");
  const priorGeneration = useRef<DatasetVersion | null>(null);
  const { start, end, vacancyId } = filters;
  const viewKey = `${mode}:${start}:${end}:${vacancyId}:${offset}`;
  const readKey = `${viewKey}:${reload}`;
  const active = read?.key === readKey || (mode === "workforce-management" && read && "data" in read &&
    read.key.startsWith(`${viewKey}:`)) ? read : null;
  const workspace = active && "data" in active ? active.data : null;
  const error = active && "error" in active ? active.error : null;
  const dataset = workspace?.dataset;
  const selected = WORKFORCE_NAVIGATION[mode];
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

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [mode, screen]);

  const screenHref = (destination: WorkforceScreen) => {
    const href = workforceModeHref(mode, previewMode, destination);
    return guide ? `${href}&scenario=${guide.name}&step=${guide.step.id}` : href;
  };
  const openScreen = (destination: WorkforceScreen) => moveTo(screenHref(destination));

  const navigate = (event: MouseEvent<HTMLAnchorElement>, href: string) => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey ||
        event.altKey || event.shiftKey) return;
    event.preventDefault();
    moveTo(href);
  };

  const startGuide = (name: GuideName) => {
    setFilters(DEFAULT_FILTERS);
    setOffset(0);
    setNotice("");
    moveTo(guideHref(name, 0));
  };

  const switchTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    storageFallbackTheme = next;
    try { window.localStorage.setItem("workforce-theme", next); } catch { /* optional */ }
    window.dispatchEvent(new Event("workforce-theme-change"));
  };

  const restricted = Boolean(error && [401, 403, 404].includes(error.status));
  const reportAccessError = useCallback((failure: WorkforceApiError) => {
    setRead((current) => current?.key.startsWith(`${viewKey}:`) ? { key: readKey, error: failure } : current);
  }, [readKey, viewKey]);
  const planningAccessError = useCallback((failure: WorkforceApiError) => {
    if (failure.status === 401 || failure.status === 403) reportAccessError(failure);
  }, [reportAccessError]);
  const interviewControls = workspace ? <InterviewGuide guide={guide} onStart={startGuide}
    onStep={(name, index) => moveTo(guideHref(name, index))}
    onExit={() => moveTo(workforceModeHref(mode, previewMode, screen))} /> : null;

  return (
    <section className={styles.root} data-theme={theme} aria-label="Workforce Intelligence demo">
      <p className={styles.disclosure}>Demo v1.0 · Prepared for an SCAS interview · Synthetic data only</p>
      <header className={styles.header}>
        <div className={styles.brand}>
          <Image className={styles.brandLogo} src="/workforce-simulation-logo.png" width={56} height={56}
            alt="Workforce Analytics Simulation Environment emblem" />
          <div><p className={styles.brandName}>Workforce & Recruitment Intelligence</p>
            <p className={styles.brandContext}>Workforce demo</p></div>
        </div>
        <div className={styles.headerActions}>
          {dataset ? <ResetDemo key={dataset.dataset_id + ":" + dataset.dataset_generation} dataset={dataset}
            onReset={(replacement) => {
              priorGeneration.current = replacement;
              setFilters(DEFAULT_FILTERS);
              setOffset(0);
              setRead(null);
              setNotice(replacement.scenario_code === "interview-core" ?
                `Demo reset. Dataset ${replacement.dataset_generation} is ready.` :
                `Full synthetic dataset is ready. Generation seed: ${replacement.generation_seed}.`);
              refresh();
            }} onConflict={() => { setNotice("The dataset changed. The workspace is refreshing."); refresh(); }}
            onAccessError={reportAccessError} /> : null}
          <button type="button" className={styles.secondaryButton} onClick={switchTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {theme === "dark" ? "Light theme" : "Dark theme"}
          </button>
          {!previewMode && onSignOut ? <button className={styles.secondaryButton} type="button"
            onClick={onSignOut}>Log Out</button> : null}
        </div>
      </header>
      <nav aria-label="Workforce sections" className={styles.navigation}>
        {WORKFORCE_MODES.map((id) => {
          const href = workforceModeHref(id, previewMode);
          return <a key={id} href={href} aria-current={mode === id ? "page" : undefined}
            className={`${styles.navItem} ${mode === id ? styles.navItemActive : ""}`}
            onClick={(event) => navigate(event, href)}>{WORKFORCE_NAVIGATION[id].label}</a>;
        })}
      </nav>

      <div className={styles.body}>
        <aside className={styles.sidebar}>
          <nav aria-label={`${selected.label} outline`} className={styles.screenMenu}>
            {selected.groups.map((group) => <div key={group.label} role="group" aria-label={group.label}>
              <p className={styles.screenGroup}>{group.label}</p>
              {group.screens.map(([id, name]) => {
                const href = screenHref(id);
                return <a key={id} href={href} aria-current={screen === id ? "page" : undefined}
                  onClick={(event) => navigate(event, href)}>{name}</a>;
              })}
            </div>)}
          </nav>
          <label className={styles.mobileSections}>Section
            <select value={screen} onChange={(event) => openScreen(event.target.value as WorkforceScreen)}>
              {selected.groups.map((group) => <optgroup key={group.label} label={group.label}>
                {group.screens.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
              </optgroup>)}
            </select>
          </label>
        </aside>
        <div className={styles.content}>
          <div className={styles.statusBar} role="status">
            <span className={`${styles.statusDot} ${dataset ? styles.statusDotReady : ""}`} aria-hidden="true" />
            {previewMode ? <span>Local UI preview — no Firebase or API calls</span> : dataset ? (
              <><span>Dataset {dataset.dataset_generation} · Revision {dataset.revision}</span>
                <span>{dataset.scenario_code === "interview-core" ? "Interview fixture" : "Full synthetic dataset"}</span>
                <span>Refreshed <time dateTime={dataset.refreshed_at}>{displayRefresh(dataset.refreshed_at)} UK</time></span>
                <button type="button" className={styles.linkButton} onClick={refresh}>Refresh data</button></>
            ) : <span>{error ? "Data unavailable" : "Loading protected data…"}</span>}
          </div>

          <section className={styles.mainContent} id="workforce-panel" aria-labelledby="workforce-heading">
            <div className={styles.pageHeadingRow}>
              <div className={styles.pageHeading}><h1 id="workforce-heading">{selected.label}</h1>
                <p>{selected.description}</p></div>
              {guide ? null : interviewControls}
            </div>
            {!restricted && notice ? <p className={styles.notice} role="status">{notice}</p> : null}
            {guide ? interviewControls : null}
            {previewMode ? <p className={styles.message}>Log In to the protected app to view and change the synthetic dataset.</p> : null}
            {error ? <div className={styles.panel} role="alert">
              <h2>{restricted ? "Workspace access unavailable" : "Unable to load this view"}</h2>
              <p>{error.status === 401 ? "Your login session has expired." : error.status === 403 ?
                "This session cannot access Workforce data." : error.status === 404 ?
                  "This workspace is currently disabled." : error.message}</p>
              {error.status === 401 ? <a href="/portfolio/workforce-intelligence">Return to demo log in</a> :
                <button type="button" className={styles.secondaryButton}
                  onClick={() => { if (error.status === 422) setFilters(DEFAULT_FILTERS); refresh(); }}>
                  {error.status === 422 ? "Restore default dates" : "Retry"}
                </button>}
            </div> : null}
            {workspace?.kind === "workforce-intelligence" ? <ExecutiveDashboard
              dashboard={workspace.dashboard} filters={filters} onFilters={setFilters} screen={screen} onOpenScreen={openScreen}
              planning={screen === "forecast" ? <ForecastPanel key={readKey} dataset={workspace.dataset}
                cutoff={workspace.dashboard.executive.executive.current_window.end} onError={planningAccessError} /> :
                screen === "scenarios" ? <ScenarioPanel key={readKey} dataset={workspace.dataset}
                  cutoff={workspace.dashboard.executive.executive.current_window.end} onError={planningAccessError} /> : null}
              pilot={screen === "insight-pilot" ? <InsightPilot key={readKey} dataset={workspace.dataset}
                window={workspace.dashboard.executive.executive.current_window} onAccessError={reportAccessError} /> : null} /> : null}
            {workspace?.kind === "workforce-management" ? <WorkforceManagement directory={workspace.directory}
              screen={screen} onOpenScreen={openScreen}
              offset={offset} onPage={setOffset} onSaved={(message) => { setNotice(message); refresh(); }}
              onConflict={() => { setNotice("The dataset or contract changed. Choose the employee again after refresh."); refresh(); }}
              initialEmployee={guide?.step.edit ? "emp-001" : undefined}
              effectiveDate={guide?.step.edit ? "2026-10-20" : undefined} onError={reportAccessError} /> : null}
            {workspace?.kind === "people-voice" ? <PeopleVoice report={workspace.report} onAccessError={reportAccessError}
              screen={screen} onOpenScreen={openScreen}
              initialCampaign={guide?.step.id === "candidate-feedback" ? "candidate-feedback" : undefined} /> : null}
            {workspace?.kind === "data-architecture" ?
              <DataArchitecture architecture={workspace.architecture} metrics={workspace.metrics}
                screen={screen} onOpenScreen={openScreen} /> : null}
          </section>
        </div>
      </div>
    </section>
  );
}
