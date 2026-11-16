/** Validated, shareable navigation state. No HR data or credentials in the URL. */
export const WORKFORCE_DEFAULT_MODE = "workforce-intelligence" as const;

export const WORKFORCE_MODES = [
  "workforce-intelligence",
  "workforce-management",
  "people-voice",
  "data-architecture",
] as const;

export type WorkforceMode = (typeof WORKFORCE_MODES)[number];

type ModeNavigation = {
  label: string;
  description: string;
  groups: readonly { label: string; screens: readonly (readonly [string, string])[] }[];
};

export const WORKFORCE_NAVIGATION = {
  "workforce-intelligence": {
    label: "Workforce Intelligence",
    description: "Recruitment performance and establishment at a glance.",
    groups: [
      { label: "Performance overview", screens: [
        ["executive", "Recruitment overview"], ["workforce-trend", "Workforce trend"], ["outcomes", "Workforce outcomes"],
      ] },
      { label: "Recruitment pipeline", screens: [
        ["vacancy-ageing", "Vacancy ageing"], ["vacancies", "Vacancy lifecycle"], ["funnel", "Candidate funnel"],
        ["attraction", "Recruitment channels"], ["equality", "Inclusive recruitment"],
      ] },
      { label: "Planning & insight", screens: [
        ["forecast", "Forecasting"], ["scenarios", "What-if scenarios"], ["insight-pilot", "Insight Pilot"],
      ] },
    ],
  },
  "workforce-management": {
    label: "Workforce Management",
    description: "Manage synthetic employment, recruitment and development records.",
    groups: [
      { label: "People & employment", screens: [
        ["directory", "People directory"], ["employee-profile", "Employee profile"], ["contracts", "Contracts & FTE"],
        ["assignment-history", "Organisational assignments"], ["learning-pdr", "Learning & PDR"], ["leavers", "Leavers"],
      ] },
      { label: "Recruitment operations", screens: [
        ["manage-vacancies", "Vacancies"], ["manage-candidates", "Candidates"],
        ["offers-checks", "Offers & checks"], ["new-starters", "New starters"],
      ] },
      { label: "Data administration", screens: [
        ["reference-data", "Reference data"], ["import-export", "Import / Export"], ["audit-history", "Audit history"],
      ] },
    ],
  },
  "people-voice": {
    label: "People Voice",
    description: "Evidence from synthetic staff surveys.",
    groups: [
      { label: "Survey setup", screens: [
        ["survey-builder", "Survey builder"], ["voice-campaigns", "Campaigns & responses"],
      ] },
      { label: "Analysis & actions", screens: [
        ["voice-analytics", "Survey analytics"], ["voice-review", "Analyst review"], ["voice-tracker", "Action tracker"],
      ] },
      { label: "Prepared example", screens: [
        ["voice-report", "Prepared report"], ["signals", "Published findings"], ["voice-actions", "Management action"],
      ] },
    ],
  },
  "data-architecture": {
    label: "Data Architecture",
    description: "Data ownership, quality and lineage.",
    groups: [
      { label: "Architecture", screens: [
        ["data-lineage", "Overview and lineage"], ["data-layers", "Data layers"], ["data-model", "Data model"],
      ] },
      { label: "Governance", screens: [
        ["quality", "Data quality"], ["sources", "Sources and assumptions"], ["catalogue", "Metric catalogue"],
      ] },
      { label: "Process", screens: [["voice-process", "People Voice BPMN"]] },
    ],
  },
} as const satisfies Record<WorkforceMode, ModeNavigation>;

export type WorkforceScreen = (typeof WORKFORCE_NAVIGATION)[WorkforceMode]["groups"][number]["screens"][number][0];
export type OpenWorkforceScreen = (screen: WorkforceScreen) => void;

export function isWorkforceMode(value: unknown): value is WorkforceMode {
  return typeof value === "string" && WORKFORCE_MODES.some((mode) => mode === value);
}

/** Reject ambiguous duplicate parameters instead of guessing a section. */
export function modeFromSearch(search: string): WorkforceMode {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const values = params.getAll("mode");
  return values.length === 1 && isWorkforceMode(values[0])
    ? values[0]
    : WORKFORCE_DEFAULT_MODE;
}

export function screenFromLocation(mode: WorkforceMode, search: string, hash = ""): WorkforceScreen {
  const values = new URLSearchParams(search).getAll("section");
  const choice = values.length === 1 ? values[0] :
    values.length === 0 && mode === "people-voice" && hash.startsWith("#response-") ? "signals" :
    values.length === 0 ? hash.slice(1) : "";
  const groups: readonly { screens: readonly (readonly [WorkforceScreen, string])[] }[] =
    WORKFORCE_NAVIGATION[mode].groups;
  return groups.flatMap((group) => group.screens).find(([id]) => id === choice)?.[0] ?? groups[0].screens[0][0];
}

/** Navigation intentionally drops unrelated URL parameters (including secrets). */
export const WORKFORCE_LOCAL_PREVIEW_PATH = "/portfolio/workforce-intelligence/preview" as const;

export function workforceModeHref(mode: WorkforceMode, previewMode = false, screen?: WorkforceScreen): string {
  const path = previewMode ? WORKFORCE_LOCAL_PREVIEW_PATH : "/portfolio/workforce-intelligence";
  return screen ? `${path}?mode=${mode}&section=${screen}` : `${path}?mode=${mode}`;
}
