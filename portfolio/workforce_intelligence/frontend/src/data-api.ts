import type { WorkforceMode } from "./mode-state";

const API = "/portfolio/workforce-intelligence/api";

export type DatasetVersion = { dataset_id: string; dataset_generation: number };
export type Dataset = DatasetVersion & {
  revision: number;
  scenario_code: string;
  seed_version: string;
  history_start: string;
  as_of_date: string;
  refreshed_at: string;
};

export type Snapshot = { dataset: Dataset; synthetic: true };
export type Window = { start: string; end: string };
export type Filters = { start: string; end: string; vacancyId: string };
export const DEFAULT_FILTERS: Filters = { start: "", end: "", vacancyId: "" };

export type MetricDefinition = {
  code: string;
  name: string;
  unit: string;
  formula: string;
  numerator: string;
  denominator: string | null;
  exclusions: string;
  grain: string;
  caveat: string;
  version: string;
  target: number | null;
};
export type Observation = {
  value: number | null;
  numerator: number | null;
  denominator: number | null;
  sample_size: number | null;
  status: "available" | "unavailable" | "suppressed";
  reason: string | null;
};
export type Comparison = {
  definition: MetricDefinition;
  current: Observation;
  previous: Observation;
  direction: "up" | "down" | "flat" | "unavailable";
};
export type Quality = Snapshot & {
  quality_status: "passed" | "review_required";
  issues: Record<string, number>;
};
export type Executive = Quality & {
  executive: { metrics: Comparison[]; current_window: Window; previous_window: Window | null };
};
export type Vacancies = Snapshot & {
  status_counts: Record<string, number>;
  items: Array<{
    id: string;
    title: string;
    status: string;
    approved_positions: number;
    filled_positions: number;
    approved_wte: number;
    filled_wte: number;
    open_wte: number;
  }>;
};
export type Funnel = Quality & {
  funnel: {
    window: Window;
    stages: Array<{
      stage: string;
      application_count: number;
      conversion_from_previous: Observation | null;
      median_days_from_previous: Observation | null;
    }>;
    application_to_start: Observation;
  };
};
export type Employee = {
  id: string;
  display_name: string;
  record_version: number;
  contracted_fte: number;
  organisation: string | null;
  location: string | null;
  role: string | null;
};
export type Directory = Snapshot & { items: Employee[]; next_offset: number | null };
export type Dashboard = { executive: Executive; vacancies: Vacancies; funnel: Funnel };
export type SurveyReport = {
  survey_id: string;
  title: string;
  question: string;
  period_start: string;
  period_end: string;
  invited: number;
  total_responses: number;
  analysable_responses: number;
  response_rate: number;
  analysis_id: string;
  analysis_label: string;
  analysed_on: string;
  findings: Array<{
    id: string; theme: string; classification: string; severity: string; summary: string;
    evidence: Array<{ response_id: string; comment: string }>;
    prevalence: number | null; review_kind: string; review_rationale: string; reviewed_on: string; published_on: string;
  }>;
  drafts: Array<{ id: string; theme: string; review_status: string }>;
  actions: Array<{ id: string; signal_id: string; title: string; assigned_team: string; status: string; due_on: string }>;
};
export type Insight = Quality & { window: Window; metric: Comparison; report_section: "executive"; limitation: string };
export type Workspace = Snapshot & (
  | { kind: "workforce-intelligence"; dashboard: Dashboard }
  | { kind: "workforce-management"; directory: Directory }
  | { kind: "people-voice"; report: SurveyReport }
  | { kind: "data-architecture"; quality: Quality; metrics: MetricDefinition[] }
);

export class WorkforceApiError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}

export function datasetVersion(dataset: DatasetVersion): DatasetVersion {
  return { dataset_id: dataset.dataset_id, dataset_generation: dataset.dataset_generation };
}

export function sameGeneration(a: DatasetVersion, b: DatasetVersion) {
  return a.dataset_id === b.dataset_id && a.dataset_generation === b.dataset_generation;
}

export async function workforceRequest<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API}/${path}`, {
      ...init, credentials: "same-origin", cache: "no-store",
      headers: { Accept: "application/json", ...init?.headers },
    });
    const data = await response.json();
    if (!response.ok) {
      const message = typeof data?.detail === "string" ? data.detail : "Workforce request failed.";
      throw new WorkforceApiError(response.status, message);
    }
    return data as T;
  } catch (error) {
    if (error instanceof WorkforceApiError || init?.signal?.aborted) throw error;
    throw new WorkforceApiError(503, "The data service is unavailable. Retry shortly.");
  }
}

export function workforceWrite<T>(path: string, method: "POST" | "PATCH", body: object) {
  return workforceRequest<T>(path, {
    method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

export function changeContractFte(dataset: Dataset, employee: Employee, day: string, fte: string) {
  return workforceWrite<Snapshot & { record_version: number }>(
    `employees/${encodeURIComponent(employee.id)}/contracts`, "PATCH", {
      ...datasetVersion(dataset), record_version: employee.record_version,
      effective_from: day, contracted_fte: fte,
    },
  );
}

export function vacancyRateInsight(window: Window) {
  return workforceWrite<Insight>("insight-pilot/query", "POST", {
    intent: "explain_vacancy_rate", as_of_date: window.end, period_start: window.start,
  });
}

export function resetWorkforceDataset(dataset: Dataset, key: string) {
  return workforceWrite<Snapshot & { reset_generation: number; replayed: boolean }>(
    "demo/reset", "POST", { ...datasetVersion(dataset), confirmed: true, idempotency_key: key },
  );
}

export async function loadWorkspace(
  mode: WorkforceMode, filters: Filters, offset: number, signal: AbortSignal,
): Promise<Workspace> {
  if (mode === "workforce-management") {
    const directory = await workforceRequest<Directory>(`employees?limit=15&offset=${offset}`, { signal });
    return { ...directory, kind: mode, directory };
  }
  if (mode === "people-voice") {
    const data = await workforceRequest<Snapshot & { report: SurveyReport }>("surveys/reports/rota-pressure", { signal });
    return { ...data, kind: mode };
  }
  if (mode === "data-architecture") {
    const [quality, { metrics }] = await Promise.all([
      workforceRequest<Quality>("data-quality", { signal }),
      workforceRequest<{ metrics: MetricDefinition[] }>("metrics", { signal }),
    ]);
    return { ...quality, kind: mode, quality, metrics };
  }

  const dates = new URLSearchParams();
  if (filters.end) dates.set("as_of_date", filters.end);
  const range = new URLSearchParams(dates);
  if (filters.start) range.set("period_start", filters.start);
  const cohort = new URLSearchParams(range);
  if (filters.vacancyId) cohort.set("vacancy_id", filters.vacancyId);

  for (let attempt = 0; attempt < 2; attempt++) {
    const [executive, vacancies, funnel] = await Promise.all([
      workforceRequest<Executive>(`analytics/executive?${range}`, { signal }),
      workforceRequest<Vacancies>(`analytics/vacancy-lifecycle?${dates}`, { signal }),
      workforceRequest<Funnel>(`analytics/candidate-funnel?${cohort}`, { signal }),
    ]);
    const dataset = executive.dataset;
    if ([vacancies, funnel].every((value) =>
      sameGeneration(dataset, value.dataset) && dataset.revision === value.dataset.revision)) {
      return { kind: mode, synthetic: true, dataset, dashboard: { executive, vacancies, funnel } };
    }
  }
  throw new WorkforceApiError(409, "The dataset changed while these reports loaded. Refresh the view.");
}
