import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { WorkforceApiError, workforceRequest, type Snapshot } from "./data-api";
import { displayCode, displayNumber } from "./format";
import type { Campaign, ReviewPriority, VoiceAnalytics, VoiceWorkspace } from "./voice-api";
import styles from "./workforce-scaffold.module.css";

const percentage = (value: number | null) => value === null ? "—" : `${displayNumber(value)}%`;
const number = (value: number | null, unit = "") => value === null ? "—" : `${displayNumber(value)}${unit}`;

export function PriorityDetails({ priority }: { priority: ReviewPriority }) {
  return <details className={styles.catalogueEntry}>
    <summary>{priority.priority_human_review ? "Priority human review · " : ""}Review priority {number(priority.score)} / 100</summary>
    <p>Orders findings for analyst review. It is not a probability or a decision about a person.</p>
    <ul>{Object.entries(priority.components).map(([component, value]) => <li key={component}>
      {displayCode(component)}: {number(value)} × {percentage(priority.weights[component] * 100)}</li>)}</ul>
    {!priority.trend_available || !priority.segment_available ? <p>Unavailable comparison inputs contribute zero.</p> : null}
    <p>{priority.version}</p>
  </details>;
}

export function VoiceAnalyticsPanel({ campaign, source, onAccessError, campaignPicker }: {
  campaign: Campaign; source: VoiceWorkspace; onAccessError: (error: WorkforceApiError) => void;
  campaignPicker: ReactNode;
}) {
  const candidate = campaign.series === "candidate";
  const defaultTheme = candidate ? "candidate-communication" : campaign.series === "development" ? "development" :
    campaign.series === "onboarding" ? "onboarding" : "workload";
  const dimension = candidate ? "organisation" : "service";
  const selectableDimensions = candidate ?
    Object.entries(source.dimensions).filter(([code]) => ["organisation", "location", "role", "pay_band", "source"].includes(code)) :
    Object.entries(source.dimensions);
  const weights = candidate ? source.weighting_dimensions.filter((code) => ["organisation", "location", "role"].includes(code)) :
    source.weighting_dimensions;
  const [query, setQuery] = useState(() => new URLSearchParams({ theme: defaultTheme, dimension, weight_by: dimension }).toString());
  const [read, setRead] = useState<{ query: string; report?: VoiceAnalytics; error?: string }>();
  const report = read?.query === query ? read.report : undefined;
  const error = read?.query === query ? read.error : undefined;
  const surveyId = campaign.survey_id;
  useEffect(() => {
    const controller = new AbortController();
    void workforceRequest<Snapshot & { report: VoiceAnalytics }>(`surveys/${surveyId}/analytics?${query}`, {
      signal: controller.signal,
    }).then(({ report }) => {
      if (!controller.signal.aborted) setRead({ query, report });
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      if (error instanceof WorkforceApiError && [401, 403].includes(error.status)) onAccessError(error);
      else setRead({ query, error: error instanceof Error ? error.message : "Analytics unavailable." });
    });
    return () => controller.abort();
  }, [surveyId, query, onAccessError]);

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams();
    new FormData(event.currentTarget).forEach((value, key) => next.set(key, String(value)));
    setQuery(next.toString());
  }

  return <section id="voice-analytics" className={styles.panel} aria-labelledby="voice-analytics-heading">
    <div className={styles.sectionHeader}><div><h2 id="voice-analytics-heading">{candidate ? "Candidate feedback report" : "Survey analytics"}</h2>
      <p>{candidate ? "Response rate, recruitment experience ratings and related application indicators." :
        "Representation, theme prevalence and independent workforce measures."}</p></div></div>
    {campaignPicker}
    <form className={styles.filterBar} onSubmit={apply}>
      <label>Theme<select name="theme" defaultValue={defaultTheme}>
        {Object.entries(source.themes).map(([code, label]) => <option value={code} key={code}>{label}</option>)}
      </select></label>
      <label>Group results by<select name="dimension" defaultValue={dimension}>
        {selectableDimensions.map(([code, label]) => <option value={code} key={code}>{label}</option>)}
      </select></label>
      <label>Weight by<select name="weight_by" defaultValue={dimension}>
        {weights.map((code) => <option value={code} key={code}>{source.dimensions[code]}</option>)}
      </select></label>
      <label>Weight minimum<input name="trim_min" type="number" min=".25" max="1" step=".05" defaultValue=".5" required /></label>
      <label>Weight maximum<input name="trim_max" type="number" min="1" max="4" step=".1" defaultValue="2" required /></label>
      <button type="submit" className={styles.secondaryButton}>Apply survey filters</button>
    </form>
    {error ? <p role="alert" className={styles.errorText}>{error}</p> : null}
    {!error && !report ? <p role="status" className={styles.message}>Calculating survey results…</p> : null}
    {report ? <>
      <p className={styles.caption}><strong>{source.themes[report.theme]}</strong> · Unweighted · {report.weighting.status}</p>
      {report.status === "suppressed" ? <p className={styles.message}>The theme estimate is suppressed under the minimum group rule ({report.minimum}).</p> : null}
      <dl className={styles.summaryFacts}>
        <div><dt>Unweighted prevalence</dt><dd>{percentage(report.unweighted)}</dd></div>
        <div><dt>Weighted prevalence</dt><dd>{percentage(report.weighted)}</dd></div>
        <div><dt>Effective sample size</dt><dd>{number(report.effective_sample)}</dd></div>
        <div><dt>Period change</dt><dd>{number(report.trend_pp, " pp")}</dd></div>
        <div><dt>Survey non-response</dt><dd>{percentage(report.nonresponse_rate)}</dd></div>
        <div><dt>Free-text non-response</dt><dd>{percentage(report.item_nonresponse_rate)}</dd></div>
      </dl>
      <p className={styles.message}>Survey weights correct group representation, not the truthfulness or importance of an individual opinion.
        They do not correct question bias or explain why people did not respond.</p>
      {report.weighting.groups.length ? <details className={styles.catalogueEntry}><summary>Weighting basis and trim range</summary>
        <p>{report.weighting.source} · Revision {report.weighting.population_revision} · {report.weighting.version}</p>
        <p>Eligible population share ÷ respondent share, trimmed to {report.weighting.trim_min}–{report.weighting.trim_max}.</p>
        <ul>{report.weighting.groups.map((row) => <li key={row.category}>
          {row.category}: {row.eligible} eligible · {row.weight} weight</li>)}</ul>
      </details> : null}
      {report.priority ? <PriorityDetails priority={report.priority} /> : null}
      {report.requires_human_attention ? <p className={styles.notice}>Potentially serious signals require priority human review.</p> : null}
      {report.theme_frequencies.length ? <details className={styles.catalogueEntry}><summary>Synthetic theme frequency</summary>
        {report.theme_frequencies.map((row) => <div className={styles.frequency} key={row.theme}>
          <span>{row.label} · {row.responses} unique responses · {row.mentions} mentions</span>
          <span className={styles.barTrack} aria-hidden="true"><span style={{ width: `${row.unweighted ?? 0}%` }} /></span>
        </div>)}
      </details> : null}
      {report.segments_suppressed ? <p className={styles.message}>The whole breakdown is hidden when a small cell could be inferred from its total.</p> : null}
      {report.segments.length ? <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Survey segment breakdown">
        <table className={styles.table}><thead><tr>
          {["Segment", "Responded / invited", "Response rate", "Theme responses", "Unweighted", "Weighted",
            "Effective sample", "Difference", "Prevalence ratio", "Period change"].map((col) => <th key={col} scope="col">{col}</th>)}
        </tr></thead><tbody>{report.segments.map((row) => <tr key={row.category}>
          <th scope="row">{row.category}</th><td>{row.responded} / {row.invited}</td><td>{percentage(row.response_rate)}</td>
          <td>{row.responses} / {row.analysable}</td><td>{percentage(row.unweighted)}</td><td>{percentage(row.weighted)}</td>
          <td>{number(row.effective_sample)}</td><td>{number(row.difference_pp, " pp")}</td>
          <td>{number(row.prevalence_ratio, "×")}</td><td>{number(row.trend_pp, " pp")}</td>
        </tr>)}</tbody></table>
      </div> : null}
      {report.ratings.length ? <details className={styles.catalogueEntry}><summary>Rating question results</summary>
        {report.ratings.map((row) => <p key={row.question}>{row.question} · {row.mean === null ? "Suppressed" :
          `${number(row.mean)}/${row.scale_max} (${row.answered} answered)`}</p>)}
      </details> : null}
      {report.triangulation.length ? <details className={styles.catalogueEntry}><summary>Independent workforce indicators</summary>
        {report.triangulation.map((row) => <p key={row.indicator}>{row.indicator}: {row.count} / {row.eligible}
          {" "}({percentage(row.percent)}). {row.relation}</p>)}
      </details> : null}
    </> : null}
  </section>;
}
