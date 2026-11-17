import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { datasetVersion, WorkforceApiError, workforceRequest, workforceWrite, type Snapshot } from "./data-api";
import { displayCode, displayDay, displayNumber } from "./format";
import type { OpenWorkforceScreen } from "./mode-state";
import { PriorityDetails } from "./VoiceAnalyticsPanel";
import type { Campaign, Signal, VoiceAction, VoiceReview, VoiceRun } from "./voice-api";
import styles from "./workforce-scaffold.module.css";

type OnAccessError = (error: WorkforceApiError) => void;
type Save = (path: string, method: "POST" | "PATCH", payload: object) => void;
const statusLabel = (value: string) => value === "awaiting_review" ? "Awaiting analyst review" : displayCode(value);
const classifications = ["Complaint", "Concern", "Safety concern", "Suggestion", "Improvement initiative",
  "Positive feedback", "Request for clarification", "Neutral observation"];
const levels = ["Low", "Medium", "High", "Critical"];
const field = (fields: FormData, key: string) => String(fields.get(key) ?? "").trim();
const failures: Record<string, string> = {
  provider_not_configured: "External AI is not configured on this host. The demonstration option is available.",
  provider_timeout: "OpenAI exceeded the analysis time limit. Retry or use the demonstration option.",
  provider_unavailable: "External AI did not complete. Retry or use the demonstration option.",
  evidence_validation_failed: "The analysis returned invalid evidence. Nothing from that run can be published.",
  interrupted: "The analysis was interrupted. Start it again or use the demonstration option.",
};

export function VoiceReviewPanel({ campaign, themes, onAccessError, screen, campaignPicker, onOpenScreen }: {
  campaign: Campaign; themes: Record<string, string>; onAccessError: OnAccessError;
  screen: "voice-review" | "voice-tracker"; campaignPicker: ReactNode;
  onOpenScreen: OpenWorkforceScreen;
}) {
  const [data, setData] = useState<VoiceReview | null>(null);
  const [selected, setSelected] = useState("");
  const [reload, setReload] = useState(0);
  const [progress, setProgress] = useState("");
  const working = Boolean(progress);
  const [error, setError] = useState("");
  const pending = useRef<{ mode: string; key: string } | null>(null);
  const surveyId = campaign.survey_id;

  useEffect(() => {
    const controller = new AbortController();
    const query = selected ? `?analysis_id=${encodeURIComponent(selected)}` : "";
    void workforceRequest<VoiceReview>(`surveys/${surveyId}/review${query}`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setData(value); })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return;
        if (failure instanceof WorkforceApiError && [401, 403].includes(failure.status)) onAccessError(failure);
        else setError(failure instanceof Error ? failure.message : "Unable to load the review workspace.");
      });
    return () => controller.abort();
  }, [surveyId, selected, reload, onAccessError]);

  async function run(operation: () => Promise<void>, message = "Working on People Voice…") {
    if (!data || working) return;
    setProgress(message); setError("");
    try {
      await operation();
    } catch (failure) {
      if (failure instanceof WorkforceApiError && [401, 403].includes(failure.status)) onAccessError(failure);
      else setError(failure instanceof Error ? failure.message : "Unable to save your change.");
    } finally { setProgress(""); }
  }

  function analyse(mode: "ai" | "demo") {
    if (!data) return;
    void run(async () => {
      if (pending.current?.mode !== mode) pending.current = { mode, key: crypto.randomUUID() };
      const { run: receipt } = await workforceWrite<Snapshot & { run: VoiceRun }>(`surveys/${surveyId}/analyse`, "POST", {
        ...datasetVersion(data.dataset), mode, idempotency_key: pending.current.key,
      });
      if (receipt.status !== "running") pending.current = null;
      setSelected(receipt.id);
      setReload((value) => value + 1);
    }, mode === "ai" ? "Analysing survey comments… This can take up to a minute." : undefined);
  }

  const save: Save = (path, method, payload) => {
    if (!data) return;
    const startingLocation = window.location.href;
    void run(async () => {
      setData(await workforceWrite<VoiceReview>(path, method, { ...datasetVersion(data.dataset), ...payload }));
      if (path.endsWith("/actions") && window.location.href === startingLocation) onOpenScreen("voice-tracker");
    });
  };

  const selectedRun = data?.selected_run;
  const feedback = <>
    {progress || (!data && !error) ? <p role="status" className={styles.message}>
      {progress || "Loading People Voice…"}
    </p> : null}
    {error ? <p role="alert" className={styles.errorText}>{error}</p> : null}
  </>;
  if (screen === "voice-tracker") return (
    <section id="voice-tracker" className={styles.panel} aria-labelledby="voice-tracker-heading">
      <h2 id="voice-tracker-heading">Action tracker</h2>
      {campaignPicker}
      {feedback}
      {data?.actions.length ? data.actions.map((action) => <TrackerCard key={`${action.id}:${action.status}`}
        action={action} working={working} save={save} />) : data ?
        <p className={styles.message}>Actions appear here after a reviewed finding is published and an action is created.</p> : null}
    </section>
  );
  return (
    <section id="voice-review" className={styles.panel} aria-labelledby="voice-review-heading">
      <div className={styles.sectionHeader}><div><h2 id="voice-review-heading">Report analysis & analyst review</h2>
        <p>Classification creates a draft. A person must review it and publish it separately.</p></div></div>
      {campaignPicker}
      <div className={styles.filterBar}>
        <button type="button" className={styles.primaryButton} disabled={!data || working || campaign.analysable < campaign.anonymity_min}
          onClick={() => analyse("ai")}>Analyse with AI</button>
        <button type="button" className={styles.secondaryButton} disabled={!data || working || campaign.analysable < campaign.anonymity_min}
          onClick={() => analyse("demo")}>Use demonstration analysis</button>
        {data?.runs.length ? <label>Analysis run<select disabled={working} value={selected || selectedRun?.id || ""}
          onChange={(event) => setSelected(event.target.value)}>
          {data.runs.map((attempt) => <option value={attempt.id} key={attempt.id}>
            {attempt.label} · {statusLabel(attempt.status)} · {displayDay(attempt.started_at)}</option>)}
        </select></label> : null}
      </div>
      {feedback}
      {campaign.analysable < campaign.anonymity_min ? <p className={styles.message}>
        Generate at least {campaign.anonymity_min} analysable comments before analysis.</p> : null}
      {selectedRun ? <div className={styles.finding}>
        <h3>{selectedRun.label}</h3>
        <p className={styles.caption}>{selectedRun.id} · {selectedRun.sample_size} selected comments · {statusLabel(selectedRun.status)}</p>
        {selectedRun.failure ? <p role="status">{failures[selectedRun.failure] ?? "Try a new analysis."}</p> : null}
        {selectedRun.status === "running" ? <button type="button" className={styles.linkButton}
          onClick={() => setReload((value) => value + 1)}>Refresh analysis</button> : null}
        {selectedRun.summary ? <p>{selectedRun.summary}</p> : null}
        <details className={styles.catalogueEntry}><summary>Analysis provenance</summary>
          <p>{selectedRun.provider} · {selectedRun.model} · Taxonomy {selectedRun.taxonomy_version} · Prompt {selectedRun.prompt_version}</p>
          <p className={styles.sourceCode}>Input hash: {selectedRun.input_hash}</p>
          {selectedRun.supersedes ? <p>Previous run: {selectedRun.supersedes}</p> : null}
        </details>
      </div> : data ? <p className={styles.message}>No analysis yet. Use the demonstration option when AI is unavailable.</p> : null}
      {data?.signals.map((signal) => <SignalCard key={`${signal.id}:${signal.state}:${signal.review_history.length}`} signal={signal}
        siblings={data.signals} themes={themes} teams={data.teams} sample={selectedRun?.sample_size ?? 0} working={working} save={save} />)}
      {selectedRun?.status === "ready" && !data?.signals.length ? <p className={styles.message}>No validated signals were identified.</p> : null}
    </section>
  );
}

function SignalCard({ signal, siblings, themes, teams, sample, working, save }: {
  signal: Signal; siblings: Signal[]; themes: Record<string, string>; teams: string[];
  sample: number; working: boolean; save: Save;
}) {
  const [decision, setDecision] = useState("confirm");
  const closed = signal.state === "published" || signal.state === "rejected";
  const edited = ["amend", "split", "merge"].includes(decision);
  const ready = signal.state === "confirmed" || signal.state === "amended";

  function decide(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const selected = values.getAll("evidence").map(String);
    save(`surveys/signals/${signal.id}/review`, "POST", {
      action: decision, rationale: field(values, "rationale"),
      theme: edited ? field(values, "theme") || undefined : undefined,
      classification: edited ? field(values, "classification") || undefined : undefined,
      severity: edited ? field(values, "severity") || undefined : undefined,
      subtheme: edited ? field(values, "subtheme") || undefined : undefined,
      keep_response_ids: edited && selected.length ? selected : undefined,
      merge_signal_id: decision === "merge" ? field(values, "merge") : undefined,
    });
  }

  return <article className={styles.finding}>
    <h3>{signal.theme}{signal.subtheme ? ` · ${signal.subtheme}` : ""}</h3>
    <p className={styles.caption}>{statusLabel(signal.state)}{signal.classification ? ` · ${signal.classification} · ${signal.severity}` : ""}</p>
    {signal.urgent ? <p className={styles.notice}>Potentially serious signal — priority human review required.</p> : null}
    {signal.publication_eligible ? <>
      <p>{signal.summary}</p>
      <p className={styles.caption}>{signal.unique_responses} of {sample} analysed comments ({displayNumber(signal.prevalence!)}%).
        This is a share of the analysed sample.</p>
      {signal.original_classification && signal.original_classification !== signal.classification ?
        <p className={styles.caption}>Original classification: {signal.original_classification}</p> : null}
      <details className={styles.catalogueEntry}><summary>Validated evidence ({signal.evidence.length})</summary>
        <ul className={styles.evidenceList}>{signal.evidence.map((row) => <li key={row.response_id}>
          <span>{row.response_id}</span><q>{row.excerpt}</q></li>)}</ul>
      </details>
      {signal.priority ? <PriorityDetails priority={signal.priority} /> : null}
    </> : <p className={styles.message}>Evidence is suppressed by the anonymity rule. This finding cannot be published.</p>}
    {signal.review_history.length ? <details className={styles.catalogueEntry}><summary>Review history</summary>
      <ol>{signal.review_history.map((event, index) => <li key={index}>
        {statusLabel(event.action)} · {displayDay(event.occurred_at)} · Demo member: {event.rationale}</li>)}</ol>
    </details> : null}
    {!closed ? <details className={styles.catalogueEntry}><summary>Review this finding</summary>
      <form className={styles.filterBar} onSubmit={decide} aria-label={`Review ${signal.theme}`}>
        <label>Decision<select value={decision} onChange={(event) => setDecision(event.target.value)}>
          <option value="confirm">Confirm</option>
          {signal.publication_eligible ? <><option value="amend">Amend</option><option value="split">Split evidence</option>
            {siblings.some((item) => item.id !== signal.id && item.publication_eligible && !["published", "rejected"].includes(item.state)) ?
              <option value="merge">Merge findings</option> : null}</> : null}
          <option value="reject">Reject</option>
          {ready && signal.publication_eligible ? <option value="publish">Publish reviewed finding</option> : null}
        </select></label>
        <label>Review rationale<input name="rationale" minLength={4} maxLength={320} required /></label>
        {edited ? <>
          <label>Theme<select name="theme" defaultValue={signal.theme_code ?? ""}>
            {Object.entries(themes).map(([code, label]) => <option value={code} key={code}>{label}</option>)}</select></label>
          <label>Subtheme (optional)<input name="subtheme" defaultValue={signal.subtheme ?? ""} maxLength={80} /></label>
          <label>Classification<select name="classification" defaultValue={signal.classification ?? ""}>
            {classifications.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Severity<select name="severity" defaultValue={signal.severity ?? ""}>
            {levels.map((value) => <option key={value}>{value}</option>)}</select></label>
          {decision === "merge" ? <label>Other finding<select name="merge" required>
            {siblings.filter((item) => item.id !== signal.id && item.publication_eligible && !["published", "rejected"].includes(item.state))
              .map((item) => <option value={item.id} key={item.id}>{item.theme}</option>)}</select></label> : null}
          {decision !== "merge" ? <fieldset key={decision} className={styles.voiceEvidence}>
            <legend>{decision === "split" ? "Evidence for the new finding" : "Validated evidence to retain"}</legend>
            {signal.evidence.map((item) => <label key={item.response_id} className={styles.inlineCheck}>
              <input type="checkbox" name="evidence" value={item.response_id} defaultChecked={decision === "amend"} />
              {item.response_id} · {item.excerpt}</label>)}
          </fieldset> : null}
        </> : null}
        <button type="submit" disabled={working} className={styles.primaryButton}>
          {decision === "publish" ? "Publish finding" : "Save decision"}</button>
      </form>
    </details> : null}
    {signal.state === "published" ? <ActionForm identity={signal.id} teams={teams} working={working} save={save} /> : null}
  </article>;
}

function ActionForm({ identity, teams, working, save }: {
  identity: string; teams: string[]; working: boolean; save: Save;
}) {
  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    save(`surveys/signals/${identity}/actions`, "POST", Object.fromEntries(values));
  }
  return <details className={styles.catalogueEntry}><summary>Create management action</summary>
    <form className={styles.filterBar} onSubmit={create}>
      <label>Action title<input name="title" minLength={4} maxLength={320} required /></label>
      <label>Responsible team<select name="team">{teams.map((team) => <option key={team}>{team}</option>)}</select></label>
      <label>Due date<input type="date" name="due_on" min={new Date().toISOString().slice(0, 10)} required /></label>
      <label>Baseline<input name="baseline" minLength={4} maxLength={320} required /></label>
      <label>Target<input name="target" minLength={4} maxLength={320} required /></label>
      <label>Expected benefit<input name="expected_benefit" minLength={4} maxLength={320} required /></label>
      <button className={styles.primaryButton} disabled={working} type="submit">Create action</button>
    </form>
  </details>;
}

function TrackerCard({ action, working, save }: { action: VoiceAction; working: boolean; save: Save }) {
  const [status, setStatus] = useState("in_progress");
  return <article className={styles.finding}>
    <h3>{action.title}</h3>
    <p className={styles.caption}>{statusLabel(action.status)} · {action.assigned_team} · Due {displayDay(action.due_on)}</p>
    <p>Baseline: {action.baseline} · Target: {action.target} · Expected benefit: {action.expected_benefit}</p>
    {action.notes ? <p>{action.notes}</p> : null}
    {action.closure_evidence ? <p><strong>Closure evidence:</strong> {action.closure_evidence}</p> : null}
    {action.status !== "closed" ? <form className={styles.filterBar} onSubmit={(event) => {
      event.preventDefault();
      const values = new FormData(event.currentTarget);
      save(`surveys/actions/${action.id}`, "PATCH", {
        status, notes: field(values, "notes"), closure_evidence: status === "closed" ? field(values, "closure") : undefined,
      });
    }}>
      <label>Action status<select value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="in_progress">In progress</option>
        {action.status === "in_progress" ? <option value="closed">Closed</option> : null}</select></label>
      <label>Progress notes<input name="notes" minLength={4} maxLength={320} required /></label>
      {status === "closed" ? <label>Closure evidence<input name="closure" minLength={4} maxLength={320} required /></label> : null}
      <button className={styles.secondaryButton} disabled={working} type="submit">Update action</button>
    </form> : null}
  </article>;
}
