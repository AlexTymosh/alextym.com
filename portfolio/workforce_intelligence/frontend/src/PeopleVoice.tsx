import type { SurveyReport, WorkforceApiError } from "./data-api";
import { displayDay, displayNumber, displayWindow } from "./format";
import { VoiceWorkspace } from "./VoiceWorkspace";
import styles from "./workforce-scaffold.module.css";

export function PeopleVoice({ report, onAccessError }: { report: SurveyReport;
  onAccessError: (error: WorkforceApiError) => void;
}) {
  return (
    <div className={styles.stack}>
      <VoiceWorkspace onAccessError={onAccessError} />
      <section id="voice-report" className={styles.panel} aria-labelledby="reviewed-report-heading">
        <div className={styles.sectionHeader}>
          <div><h2 id="reviewed-report-heading">{report.title}</h2>
            <p>{displayWindow({ start: report.period_start, end: report.period_end })} · {report.survey_id}</p></div>
          <span className={styles.statusBadge}>{report.analysis_label}</span>
        </div>
        <dl className={styles.summaryFacts}>
          <div><dt>Responses</dt><dd>{report.total_responses} of {report.invited}</dd></div>
          <div><dt>Response rate</dt><dd>{displayNumber(report.response_rate)}%</dd></div>
          <div><dt>Analysable comments</dt><dd>{report.analysable_responses}</dd></div>
        </dl>
        <p className={styles.caption}>Survey question · {report.question}</p>
        <p className={styles.caption}>All responses describe a fictional workforce cohort.</p>
      </section>
      <section id="signals" className={styles.panel} aria-labelledby="reviewed-signals-heading">
        <div className={styles.sectionHeader}><div><h2 id="reviewed-signals-heading">Published findings</h2>
          <p>{report.analysis_id} · Analysed {displayDay(report.analysed_on)}</p></div></div>
        <p className={styles.message}>AI-identified signals require analyst review before operational or workforce decisions are made.</p>
        {report.findings.length ? report.findings.map((finding) => (
          <article key={finding.id} className={styles.finding}>
            <h3>{finding.theme}</h3><p className={styles.caption}>{finding.classification} · {finding.severity}</p>
            <p>{finding.summary}</p>
            <div className={styles.frequency}>
              <strong>{finding.evidence.length} of {report.analysable_responses} comments</strong>
              <span>{finding.prevalence === null ? "Not available" : `${displayNumber(finding.prevalence)}%`}</span>
              <span className={styles.barTrack} aria-hidden="true"><span style={{ width: `${finding.prevalence ?? 0}%` }} /></span>
            </div>
            <p className={styles.caption}><strong>{finding.review_kind}</strong> · Confirmed {displayDay(finding.reviewed_on)} · Published {displayDay(finding.published_on)}</p>
            <p className={styles.caption}>{finding.review_rationale}</p>
            <ul className={styles.evidenceLinks} aria-label={`Evidence for ${finding.theme}`}>
              {finding.evidence.map((item) => <li key={item.response_id}>
                <a href={`#response-${item.response_id}`}>{item.response_id}</a>
              </li>)}
            </ul>
            <ul className={styles.evidenceList} aria-label="Synthetic evidence excerpts">
              {finding.evidence.map((item) => <li key={item.response_id} id={`response-${item.response_id}`} tabIndex={-1}>
                <span>{item.response_id}</span><q>{item.comment}</q>
              </li>)}
            </ul>
          </article>
        )) : <p className={styles.message}>This report has no published findings.</p>}
        {report.drafts.length ? <details className={styles.planned}>
          <summary>Unpublished drafts ({report.drafts.length})</summary>
          {report.drafts.map((draft) => <p key={draft.id}>{draft.theme} · {draft.review_status}</p>)}
        </details> : null}
      </section>
      {report.actions.length ? <section id="voice-actions" className={styles.panel} aria-labelledby="voice-actions-heading">
        <div className={styles.sectionHeader}><h2 id="voice-actions-heading">Linked management action</h2></div>
        {report.actions.map((action) => <article className={styles.finding} key={action.id}>
          <h3>{action.title}</h3><p className={styles.caption}>{action.status} · {action.assigned_team} · Due {displayDay(action.due_on)} · {action.signal_id}</p>
        </article>)}
      </section> : null}
    </div>
  );
}
