import { useId, useRef, useState } from "react";
import styles from "./workforce-scaffold.module.css";

const lanes = [
  "Employee / Candidate", "People Team", "Data & Analytics", "AI Service",
  "Analyst Reviewer", "Manager / Action Owner", "Governance",
];
type Exception = { label: string; route: string };
type Activity = {
  lane: number; title: string; detail: string;
  kind?: "event" | "decision"; exceptions?: Exception[];
};

const steps: Activity[] = [
  { lane: 1, title: "Start", kind: "event", detail: "People Team identifies a question for the synthetic listening campaign." },
  { lane: 1, title: "Create survey", detail: "Choose an audience, dates and question options in Survey builder." },
  { lane: 6, title: "Approve questions", detail: "Confirm question wording and scope as part of the demo's governance walkthrough. Survey builder saves the chosen questions." },
  { lane: 1, title: "Open campaign", detail: "Create the synthetic campaign with an invited cohort and the configured minimum sample." },
  { lane: 0, title: "Collect responses", detail: "Generate repeatable fictional responses. Invited participants and non-respondents count toward representativeness." },
  { lane: 2, title: "Minimise and redact", detail: "Use approved thematic inputs and redact identifiers before comments go to AI review." },
  { lane: 2, title: "Anonymity threshold met?", kind: "decision", detail: "Check the analysable population and suppress small groups before interpretation.",
    exceptions: [{ label: "Insufficient responses", route: "Suppress the result. Gather more synthetic responses and repeat the anonymity check." }] },
  { lane: 3, title: "Run thematic analysis", detail: "Classify eligible comments and propose candidate signals with response IDs.",
    exceptions: [{ label: "AI API failure", route: "Use the labelled demonstration fallback or retry a recoverable provider failure." }] },
  { lane: 2, title: "Structured evidence valid?", kind: "decision", detail: "Validate JSON, evidence IDs against the selected campaign and excerpts against the redacted comments.",
    exceptions: [
      { label: "Invalid JSON", route: "Block the provider result and record the failed attempt. Use a new validated run for review." },
      { label: "Unsupported evidence", route: "Block publication. Resolve unsupported IDs or excerpts before a new review." },
    ] },
  { lane: 4, title: "Review signals", detail: "Read evidence, consider representation and record rationale before a decision.",
    exceptions: [{ label: "Urgent human review", route: "Review urgent evidence immediately. The signal still needs a human decision and separate publication." }] },
  { lane: 4, title: "Confirm, amend or reject?", kind: "decision", detail: "Confirm evidence or amend the finding. Split or merge where appropriate before approving.",
    exceptions: [{ label: "Analyst rejection", route: "Keep the rejected item and rationale in the review history. End this publication path." }] },
  { lane: 6, title: "Publish approved finding", detail: "Publish separately after approval. Gold requires valid evidence and an earlier reviewer decision." },
  { lane: 5, title: "Assign an action", detail: "Select an owner team, due date, baseline and target for a published finding." },
  { lane: 5, title: "Monitor target and progress", detail: "Record status and progress against the target in the action tracker.",
    exceptions: [{ label: "Action overdue", route: "Use the due date and current status to identify an overdue action. Escalation is illustrated in the demo and handled by the owner." }] },
  { lane: 1, title: "Communicate outcome", detail: "Summarise the agreed action and result for the audience. This communication is a walkthrough step." },
  { lane: 5, title: "Close feedback loop", detail: "Record closure evidence. Use the outcome to inform the next campaign." },
  { lane: 6, title: "End", kind: "event", detail: "The findings, reviewer rationale and action history remain available for the dataset generation." },
];

const labelWidth = 156;
const column = 160;
const row = 119;
const nodeWidth = 128;
const width = labelWidth + steps.length * column;
const height = lanes.length * row;
const zoomLevels = [75, 100, 125];
const x = (index: number) => labelWidth + 12 + index * column;
const y = (step: Activity) => step.lane * row + 39;

export function VoiceProcess() {
  const [selected, setSelected] = useState(0);
  const [zoom, setZoom] = useState(100);
  const viewport = useRef<HTMLDivElement>(null);
  const arrow = useId();
  const step = steps[selected];
  const scale = zoom / 100;

  function choose(index: number) {
    setSelected(index);
    const panel = viewport.current;
    if (panel) panel.scrollTo({
      left: (x(index) + nodeWidth / 2) * scale - panel.clientWidth / 2,
      top: y(steps[index]) * scale - panel.clientHeight / 2,
    });
  }

  return <section id="voice-process" aria-labelledby="process-heading" className={styles.panel}>
    <div className={styles.sectionHeader}><div>
      <h2 id="process-heading">People Voice to Action</h2>
      <p>BPMN walkthrough of the synthetic campaign, analyst publication and management follow-up.</p>
    </div></div>
    <div className={styles.diagramControls} aria-label="Process diagram controls" role="group">
      <button type="button" className={styles.secondaryButton} disabled={selected === 0}
        onClick={() => choose(selected - 1)}>Previous activity</button>
      <button type="button" className={styles.secondaryButton} disabled={selected === steps.length - 1}
        onClick={() => choose(selected + 1)}>Next activity</button>
      <label className={styles.control}>Diagram zoom<select value={zoom} onChange={(event) => {
        const next = Number(event.currentTarget.value);
        const panel = viewport.current;
        if (panel) {
          const { scrollLeft, scrollTop } = panel;
          requestAnimationFrame(() => panel.scrollTo({ left: scrollLeft * next / zoom, top: scrollTop * next / zoom }));
        }
        setZoom(next);
      }}>{zoomLevels.map((level) => <option key={level} value={level}>{level}%</option>)}</select></label>
    </div>
    <p className={styles.caption}>Scroll across the lanes or use the activity controls. Decisions and exceptions are labelled.</p>
    <div className={styles.processViewport} role="region" aria-label="Scrollable People Voice BPMN" tabIndex={0} ref={viewport}>
      <div style={{ width: width * scale, height: height * scale, position: "relative" }}>
        <div className={styles.processBoard} style={{ width, height, transform: `scale(${scale})` }}>
          <div aria-hidden="true">
            {lanes.map((name, index) => <div key={name} className={styles.processLane}
              style={{ top: index * row, height: row }}><span style={{ width: labelWidth }}>{name}</span></div>)}
            <svg className={styles.processFlows} viewBox={`0 0 ${width} ${height}`}>
              <defs><marker id={arrow} markerWidth="6" markerHeight="6" refX="6" refY="3"
                orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="var(--wi-accent)" /></marker></defs>
              {steps.slice(0, -1).map((item, i) => {
                const next = steps[i + 1];
                return <path key={item.title} d={`M${x(i) + nodeWidth} ${y(item)} H${x(i) + nodeWidth + 16} V${y(next)} H${x(i + 1)}`}
                  fill="none" stroke="var(--wi-accent)" strokeWidth="2" markerEnd={`url(#${arrow})`} />;
              })}
            </svg>
          </div>
          {steps.map((activity, index) => <div key={activity.title} className={styles.processActivity}
            style={{ top: y(activity) - 26, left: x(index), width: nodeWidth }}>
            <button type="button" className={styles.processNode} data-kind={activity.kind ?? "task"}
              data-end={index === steps.length - 1 ? "true" : undefined}
              aria-label={`${activity.title}, ${lanes[activity.lane]}`} aria-pressed={selected === index}
              aria-controls="process-activity" onClick={() => choose(index)}>{activity.title}</button>
            {activity.exceptions?.length ? <button type="button" className={styles.exceptionLink}
              aria-label={`Show exceptions for ${activity.title}`} aria-controls="process-activity"
              onClick={() => choose(index)}>Exception path{activity.exceptions.length > 1 ? "s" : ""}</button> : null}
          </div>)}
        </div>
      </div>
    </div>
    <div id="process-activity" className={styles.processDetail} aria-live="polite">
      <p className={styles.caption}>{lanes[step.lane]} · Activity {selected + 1} of {steps.length}</p>
      <h3>{step.title}</h3><p>{step.detail}</p>
      {step.exceptions?.length ? <ul>{step.exceptions.map(({ label, route }) => <li key={label}>
        <strong>{label}</strong> · {route}
      </li>)}</ul> : null}
    </div>
    <details className={styles.catalogueEntry}>
      <summary>Process as a list</summary>
      <ol className={styles.processOutline}>{steps.map((activity) => <li key={activity.title}>
        <strong>{activity.title}</strong> · {lanes[activity.lane]}. {activity.detail}
        {activity.exceptions?.length ? <ul>{activity.exceptions.map(({ label, route }) =>
          <li key={label}><strong>{label}</strong> · {route}</li>)}</ul> : null}
      </li>)}</ol>
    </details>
  </section>;
}
