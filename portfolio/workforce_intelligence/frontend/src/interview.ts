import { modeFromSearch, workforceModeHref, type WorkforceMode, type WorkforceScreen } from "./mode-state";

type Step = {
  id: string;
  mode: WorkforceMode;
  target: WorkforceScreen;
  title: string;
  instruction: string;
  edit?: boolean;
};

const overview: Step = {
  id: "overview", mode: "workforce-intelligence", target: "executive", title: "Read the starting position",
  instruction: "Show Workforce gap and Median time to hire. These values come from the current synthetic dataset.",
};
const edit: Step = {
  id: "edit-fte", mode: "workforce-management", target: "contracts", title: "Record a contract change",
  instruction: "For James W., enter 0.8 FTE effective 20 October 2026 and select Save FTE.", edit: true,
};
const refresh: Step = {
  id: "updated-gap", mode: "workforce-intelligence", target: "executive", title: "Check the revised gap",
  instruction: "Compare Workforce gap with the starting value. From the seed, it increases by 0.2 WTE.",
};
const pilot: Step = {
  id: "explain-rate", mode: "workforce-intelligence", target: "insight-pilot", title: "Ask Insight Pilot",
  instruction: "Select Explain the vacancy rate to show the calculation, period and underlying WTE figures.",
};

const extended = [
  overview, edit, refresh,
  { id: "funnel", mode: "workforce-intelligence", target: "funnel", title: "Follow the application cohort",
    instruction: "Compare distinct applications at each stage. Select Advisor intake to narrow the cohort." },
  { id: "candidate-feedback", mode: "people-voice", target: "voice-analytics", title: "Review candidate experience",
    instruction: "Open Rating question results in the prepared candidate campaign. Show the sample and contrast survey feedback with recorded application indicators." },
  { id: "voice-report", mode: "people-voice", target: "voice-report", title: "Open the People Voice report",
    instruction: "Show the response count and the labelled demonstration fallback." },
  { id: "evidence", mode: "people-voice", target: "signals", title: "Trace the signal to evidence",
    instruction: "Open response rota-001 from the evidence list, then point out the review and linked action." },
  { id: "definition", mode: "workforce-intelligence", target: "executive", title: "Inspect the metric definition",
    instruction: "Open the Workforce gap definition to see its components, reporting dates and version." },
  { id: "forecast", mode: "workforce-intelligence", target: "forecast", title: "Compare forecast models",
    instruction: "Enable forecast. With the full dataset, point out the forecast boundary and seasonal baseline error. With the short fixture, show the history requirement." },
  pilot,
  { id: "lineage", mode: "data-architecture", target: "data-lineage", title: "Trace the data to Gold",
    instruction: "Follow a contract from the operational source to the reporting model. Open Data layers to inspect a live example." },
] satisfies Step[];

export const INTERVIEW_GUIDES = {
  quick: { label: "90-second walkthrough", steps: [overview, edit, refresh, pilot] },
  extended: { label: "Five-minute walkthrough", steps: extended },
  full: { label: "Ten-minute walkthrough", steps: [
    ...extended,
    { id: "workbook", mode: "workforce-management", target: "import-export", title: "Preview an Excel import",
      instruction: "Upload the prepared synthetic workbook and validate it. Show row results and projected KPI impact." },
    { id: "scenario", mode: "workforce-intelligence", target: "scenarios", title: "Test a recruitment scenario",
      instruction: "Shorten pre-employment checks or change offer acceptance. Run the scenario and compare starts and WTE with the reference." },
    { id: "review", mode: "people-voice", target: "voice-review", title: "Review and publish evidence",
      instruction: "Choose a generated campaign, run the demonstration analysis and inspect evidence IDs. Confirm a supported finding, publish it and create a management action." },
    { id: "action", mode: "people-voice", target: "voice-tracker", title: "Assign a management action",
      instruction: "Open the action in the tracker, then record progress against its target." },
    { id: "process", mode: "data-architecture", target: "voice-process", title: "Walk through People Voice to Action",
      instruction: "Use Next activity or pick a node. Show the evidence decision and its exception paths." },
    { id: "audit", mode: "workforce-management", target: "audit-history", title: "Check audit history",
      instruction: "Look for the recorded contract edit or an approved survey decision and its request reference." },
    { id: "quality", mode: "data-architecture", target: "quality", title: "Check the data-quality rules",
      instruction: "Confirm the cutoff and revision. Show how each reconciliation check relates to reported metrics." },
  ] },
} satisfies Record<string, { label: string; steps: Step[] }>;

export type GuideName = keyof typeof INTERVIEW_GUIDES;
export type GuidePosition = { name: GuideName; index: number; step: Step };

export function isGuideName(value: string): value is GuideName {
  return Object.hasOwn(INTERVIEW_GUIDES, value);
}

export function readGuide(search: string): GuidePosition | null {
  const params = new URLSearchParams(search);
  const names = params.getAll("scenario");
  const ids = params.getAll("step");
  if (names.length !== 1 || ids.length !== 1 || !isGuideName(names[0])) return null;
  const name = names[0];
  const steps: readonly Step[] = INTERVIEW_GUIDES[name].steps;
  const index = steps.findIndex((step) => step.id === ids[0] && step.mode === modeFromSearch(search));
  return index < 0 ? null : { name, index, step: steps[index] };
}

export function guideHref(name: GuideName, index: number) {
  const step = INTERVIEW_GUIDES[name].steps[index];
  return `${workforceModeHref(step.mode)}&scenario=${name}&step=${step.id}`;
}
