import { useEffect, useState, type FormEvent } from "react";
import { datasetVersion, WorkforceApiError, workforceWrite } from "./data-api";
import { displayCode, displayWindow } from "./format";
import { VoiceAnalyticsPanel } from "./VoiceAnalyticsPanel";
import { VoiceReviewPanel } from "./VoiceReviewPanel";
import { loadVoice, type Campaign, type CampaignResponse, type VoiceWorkspace as VoiceData } from "./voice-api";
import styles from "./workforce-scaffold.module.css";

type OnError = (error: WorkforceApiError) => void;
const text = (fields: FormData, key: string) => String(fields.get(key) ?? "").trim();
const optionalNumber = (fields: FormData, key: string) => text(fields, key) ? Number(text(fields, key)) : undefined;

export function VoiceWorkspace({ onAccessError, initialCampaign = "" }: {
  onAccessError: OnError; initialCampaign?: string;
}) {
  const [data, setData] = useState<VoiceData>();
  const [selected, setSelected] = useState(initialCampaign);
  const [series, setSeries] = useState("development");
  const [showControls, setShowControls] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void loadVoice(controller.signal).then((value) => {
      if (!controller.signal.aborted) {
        setData(value);
        setSelected((current) => value.campaigns.some((item) => item.survey_id === current)
          ? current : value.campaigns[0]?.survey_id ?? "");
      }
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      if (error instanceof WorkforceApiError && [401, 403].includes(error.status)) onAccessError(error);
      else setFailure(error instanceof Error ? error.message : "Survey workspace unavailable.");
    });
    return () => controller.abort();
  }, [onAccessError, reload]);

  const campaign = data?.campaigns.find((item) => item.survey_id === selected);
  const bankComments = data?.bank.filter((item) => item.kind === "comment") ?? [];
  const bankRatings = data?.bank.filter((item) => item.kind === "rating") ?? [];
  const candidateTemplate = series === "candidate";

  async function run(path: string, payload: object, outcome: string) {
    if (!data || busy) return;
    setBusy(true);
    setMessage("");
    setFailure("");
    try {
      const result = await workforceWrite<CampaignResponse>(path, "POST", {
        ...datasetVersion(data.dataset), ...payload,
      });
      setData((current) => current && { ...current, dataset: result.dataset, campaigns: [
        result.campaign, ...current.campaigns.filter((item) => item.survey_id !== result.campaign.survey_id),
      ] });
      setSelected(result.campaign.survey_id);
      setMessage(outcome);
    } catch (error) {
      if (error instanceof WorkforceApiError && [401, 403].includes(error.status)) onAccessError(error);
      else setFailure(error instanceof Error ? error.message : "Survey request failed.");
    } finally { setBusy(false); }
  }

  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data) return;
    const fields = new FormData(event.currentTarget);
    const surveyId = text(fields, "id") || `survey-${crypto.randomUUID().slice(0, 8)}`;
    const template = bankComments.find((question) => question.code === text(fields, "comment"));
    const prompt = text(fields, "custom") || template?.prompt;
    const rating = bankRatings.find((question) => question.code === text(fields, "rating"));
    if (!prompt) return;
    void run("surveys", {
      survey_id: surveyId, title: text(fields, "title"), audience: candidateTemplate ? "candidates" : text(fields, "audience"),
      organisation_id: text(fields, "unit") || null, series, anonymity_min: Number(text(fields, "anonymity")),
      period_start: text(fields, "start"), period_end: text(fields, "end"), invited: optionalNumber(fields, "invited"),
      questions: [{ code: template?.code ?? "feedback", kind: "comment", prompt },
        ...(rating ? [{ ...rating, scale_max: Number(text(fields, "scale")) }] : [])],
    }, "Campaign created. Generate synthetic responses to start the report.");
  }

  function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!campaign) return;
    const fields = new FormData(event.currentTarget);
    const button = (event.nativeEvent as SubmitEvent).submitter;
    const mode = button instanceof HTMLButtonElement ? button.value : "balanced";
    const value = (key: string, fallback: number) => optionalNumber(fields, key) ?? fallback;
    void run(`surveys/${campaign.survey_id}/generate`, {
      mode, seed: optionalNumber(fields, "seed"), count: Number(text(fields, "count")),
      analysable_percent: value("analysable", 95), positive_percent: value("positive", mode === "significant" ? 12 : 24),
      negative_percent: value("negative", mode === "significant" ? 82 : 58),
      theme_percent: value("prevalence", mode === "significant" ? 92 : 74),
      ambiguous_percent: value("ambiguous", 4), severity: text(fields, "severity") || undefined,
    }, "Synthetic responses generated.");
  }

  if (!data) return <section id="survey-builder" className={styles.panel}>
    <h2>Survey builder</h2>
    {failure ? <p role="alert">{failure} <button type="button" className={styles.linkButton}
      onClick={() => { setFailure(""); setReload((value) => value + 1); }}>Retry</button></p> :
      <p role="status">Loading survey workspace…</p>}
  </section>;

  const day = data.dataset.as_of_date;
  const start = day.slice(0, 8) + "01";
  return <>
    <details id="survey-builder" className={styles.panel}>
      <summary className={styles.operationHeading}>Survey builder & question bank</summary>
      <p className={styles.message}>Create a synthetic campaign. Choose a question from the bank or write your own.</p>
      <form className={styles.filterBar} aria-label="Create survey campaign" onSubmit={create}>
        <label>Report template<select value={series} onChange={(event) => setSeries(event.target.value)}>
          {Object.entries(data.series).map(([code, title]) => <option key={code} value={code}>{title}</option>)}
        </select></label>
        <label>Campaign name<input name="title" key={series} defaultValue={data.series[series]} maxLength={160} required /></label>
        <label>Survey code (optional)<input name="id" maxLength={64} pattern="[a-z0-9][a-z0-9\-]{0,63}" /></label>
        <label>Audience<select name="audience" key={series} defaultValue={candidateTemplate ? "candidates" :
          series === "onboarding" ? "new_starters" : "employees"}>
          {candidateTemplate ? <option value="candidates">Candidate applications received in period</option> : <>
            <option value="employees">Current workforce</option><option value="new_starters">New starters, first year</option>
            <option value="exit">Leavers in period</option>
          </>}
        </select></label>
        <label>Service area<select name="unit"><option value="">All service areas</option>
          {data.units.map((unit) => <option key={unit.id} value={unit.id}>{unit.label}</option>)}</select></label>
        <label>Survey starts<input name="start" type="date" min={data.dataset.history_start} max={day} defaultValue={start} required /></label>
        <label>Survey ends<input name="end" type="date" min={data.dataset.history_start} max={day} defaultValue={day} required /></label>
        <label>Invitations (blank for all)<input name="invited" type="number" min="5" max="5000" /></label>
        <label>Anonymity minimum<input name="anonymity" type="number" min="5" max="30" defaultValue="5" required /></label>
        <label>Free-text question<select name="comment" key={series} defaultValue={series === "general" ? "experience" : series}>
          {bankComments.map((question) => <option key={question.code} value={question.code}>{question.prompt}</option>)}</select></label>
        <label>Replace with a custom question<input name="custom" minLength={4} maxLength={160} /></label>
        <label>Optional rating question<select name="rating" defaultValue="support"><option value="">None</option>
          {bankRatings.map((question) => <option key={question.code} value={question.code}>{question.prompt}</option>)}</select></label>
        <label>Rating scale<select name="scale"><option value="5">1–5</option><option value="7">1–7</option></select></label>
        <button className={styles.primaryButton} type="submit" disabled={busy}>Create campaign</button>
      </form>
    </details>
    <section id="voice-campaigns" className={styles.panel} aria-labelledby="campaigns-heading">
      <div className={styles.sectionHeader}><div><h2 id="campaigns-heading">Campaigns & response monitor</h2>
        <p>Eligible people, invitations and responses are counted separately.</p></div></div>
      {!data.campaigns.length ? <p className={styles.message}>Create a campaign above, or open the ready-to-show report below.</p> :
        <label className={styles.control}>Campaign<select value={selected} onChange={(event) => {
          setSelected(event.target.value); setFailure(""); setMessage("");
        }}>{data.campaigns.map((item) => <option key={item.survey_id} value={item.survey_id}>{item.title} · {item.survey_id}</option>)}</select></label>}
      {message ? <p role="status" className={styles.notice}>{message}</p> : null}
      {failure ? <p role="alert" className={styles.errorText}>{failure}</p> : null}
      {campaign ? <ResponseMonitor campaign={campaign} /> : null}
      {campaign && !campaign.generated_at ? <form className={styles.filterBar} onSubmit={generate} key={campaign.survey_id}
        aria-label="Generate synthetic survey responses">
        <label>Response count<input name="count" type="number" min={5} max={Math.min(240, campaign.invited)}
          defaultValue={Math.min(160, campaign.invited)} required /></label>
        <label>Seed (blank for default)<input name="seed" type="number" min="0" max="4294967295" step="1" /></label>
        <button type="button" className={styles.linkButton} aria-expanded={showControls} onClick={() => setShowControls((value) => !value)}>
          {showControls ? "Hide sample controls" : "Sample controls"}</button>
        {showControls ? <>
          {[["analysable", "Analysable text %", 95], ["positive", "Positive %", 24], ["negative", "Negative %", 58],
            ["prevalence", "Target concern %", 74], ["ambiguous", "Ambiguous text %", 4]].map(([code, label, value]) =>
              <label key={code}>{label}<input name={String(code)} type="number" min="0" max="100" defaultValue={value} /></label>)}
          <label>Concern severity<select name="severity"><option value="">Scenario default</option>
            {["Low", "Medium", "High", "Critical"].map((level) => <option key={level}>{level}</option>)}</select></label>
        </> : null}
        <button className={styles.primaryButton} disabled={busy} value="balanced" type="submit">Generate balanced sample</button>
        <button className={styles.secondaryButton} disabled={busy} value="emerging" type="submit">Generate emerging concern</button>
        <button className={styles.secondaryButton} disabled={busy} value="significant" type="submit">Generate significant concern</button>
        <button className={styles.secondaryButton} disabled={busy} value="exploratory" type="submit">Generate exploratory sample</button>
      </form> : null}
    </section>
    {campaign?.generated_at ? <VoiceAnalyticsPanel key={campaign.survey_id}
      campaign={campaign} source={data} onAccessError={onAccessError} /> : null}
    {campaign?.generated_at ? <VoiceReviewPanel key={campaign.survey_id}
      campaign={campaign} themes={data.themes} onAccessError={onAccessError} /> : null}
  </>;
}

function ResponseMonitor({ campaign }: { campaign: Campaign }) {
  return <div className={styles.finding}>
    <h3>{campaign.title}</h3>
    <p className={styles.caption}>{displayWindow({ start: campaign.period_start, end: campaign.period_end })} · {campaign.survey_id}
      {campaign.generation_mode ? ` · ${displayCode(campaign.generation_mode)} · Seed ${campaign.generation_seed}` : " · Awaiting responses"}</p>
    {campaign.series === "candidate" ? <p className={styles.caption}>
      The eligible unit is one synthetic application. Interview ratings cover applicants with a recorded interview.
    </p> : null}
    <dl className={styles.summaryFacts}>
      <div><dt>Eligible</dt><dd>{campaign.eligible}</dd></div><div><dt>Invited</dt><dd>{campaign.invited}</dd></div>
      <div><dt>Responses</dt><dd>{campaign.responses}</dd></div><div><dt>Analysable comments</dt><dd>{campaign.analysable}</dd></div>
      <div><dt>Response rate</dt><dd>{(100 * campaign.responses / campaign.invited).toFixed(1)}%</dd></div>
    </dl>
    <p className={styles.message}>People who did not respond may have different experiences. Non-response does not imply a view.</p>
  </div>;
}
