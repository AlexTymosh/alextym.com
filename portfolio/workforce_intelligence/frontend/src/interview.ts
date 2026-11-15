import { modeFromSearch, workforceModeHref, type WorkforceMode } from "./mode-state";

type Step = {
  id: string;
  mode: WorkforceMode;
  target: string;
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
  instruction: "For Demo A., enter 0.8 FTE effective 20 October 2026 and select Save FTE.", edit: true,
};
const refresh: Step = {
  id: "updated-gap", mode: "workforce-intelligence", target: "executive", title: "Check the revised gap",
  instruction: "Compare Workforce gap with the starting value. From the seed, it increases by 0.2 WTE.",
};
const pilot: Step = {
  id: "explain-rate", mode: "workforce-intelligence", target: "insight-pilot", title: "Ask Insight Pilot",
  instruction: "Select Explain the vacancy rate to show the calculation, period and underlying WTE figures.",
};

export const INTERVIEW_GUIDES = {
  quick: { label: "90-second walkthrough", steps: [overview, edit, refresh, pilot] },
  extended: { label: "Five-minute walkthrough", steps: [
    overview, edit, refresh,
    { id: "funnel", mode: "workforce-intelligence", target: "funnel", title: "Follow the application cohort",
      instruction: "Compare the distinct applications at each stage. Select Advisor intake to narrow the cohort." },
    { id: "voice-report", mode: "people-voice", target: "voice-report", title: "Open the People Voice report",
      instruction: "Show the response count and the labelled demonstration fallback." },
    { id: "evidence", mode: "people-voice", target: "signals", title: "Trace the signal to evidence",
      instruction: "Open response rota-001 from the evidence list, then point out the review and linked action." },
    { id: "definition", mode: "workforce-intelligence", target: "executive", title: "Inspect the metric definition",
      instruction: "Open the Workforce gap definition to see its components and version. The vacancy selector filters the application funnel." },
    pilot,
    { id: "lineage", mode: "data-architecture", target: "data-lineage", title: "Trace the data to Gold",
      instruction: "Follow the employment and starter tables through Bronze and Silver to the governed reports." },
  ] },
} satisfies Record<string, { label: string; steps: Step[] }>;

export type GuideName = keyof typeof INTERVIEW_GUIDES;
export type GuidePosition = { name: GuideName; index: number; step: Step };

export function readGuide(search: string): GuidePosition | null {
  const params = new URLSearchParams(search);
  const names = params.getAll("scenario");
  const ids = params.getAll("step");
  if (names.length !== 1 || ids.length !== 1 || (names[0] !== "quick" && names[0] !== "extended")) return null;
  const name = names[0];
  const steps: readonly Step[] = INTERVIEW_GUIDES[name].steps;
  const index = steps.findIndex((step) => step.id === ids[0] && step.mode === modeFromSearch(search));
  return index < 0 ? null : { name, index, step: steps[index] };
}

export function guideHref(name: GuideName, index: number) {
  const step = INTERVIEW_GUIDES[name].steps[index];
  return `${workforceModeHref(step.mode)}&scenario=${name}&step=${step.id}`;
}
