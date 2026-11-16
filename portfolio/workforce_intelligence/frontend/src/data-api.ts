import type { WorkforceMode } from "./mode-state";

const API = "/portfolio/workforce-intelligence/api";
export const XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
export const MAX_WORKBOOK_BYTES = 1024 * 1024;

export type DatasetVersion = { dataset_id: string; dataset_generation: number };
export type Dataset = DatasetVersion & {
  revision: number;
  scenario_code: string;
  generation_seed: number;
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
export type Architecture = Quality & {
  as_of_date: string;
  layers: Array<{
    code: "operational" | "bronze" | "silver" | "gold";
    relation: string;
    values: Record<string, string | number | null>;
  }>;
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
export type RecruitmentSourceRow = {
  source_code: string;
  applications: number;
  screened: number;
  shortlisted: number;
  interviewed: number;
  accepted_offers: number;
  starters: number;
  application_to_start_percent: number | null;
};
export type RecruitmentSources = Snapshot & {
  report: {
    window: Window;
    campaign_id: string | null;
    organisation_id: string | null;
    location_id: string | null;
    role_id: string | null;
    rows: RecruitmentSourceRow[];
    total_applications: number;
  };
};
export type WorkforceTrendPoint = {
  month_key: string;
  as_of_date: string;
  partial_period: boolean;
  budgeted_wte: number | null;
  substantive_wte: number;
  workforce_gap_wte: number | null;
  new_starters: number;
  leavers: number;
};
export type WorkforceTrendReport = Quality & {
  trend: { window: Window; points: WorkforceTrendPoint[] };
};
export type VacancyAgeingReport = Quality & {
  ageing: {
    as_of_date: string;
    bands: Array<{ code: string; label: string; requisitions: number; open_wte: number }>;
    total_open_requisitions: number;
    total_open_wte: number;
    oldest_open: Array<{
      id: string; title: string; status: string; approved_on: string;
      age_days: number; open_wte: number;
    }>;
  };
};
export type InclusiveRecruitmentGroup = {
  code: string;
  applications: number | null;
  screened: number | null;
  shortlisted: number | null;
  interviewed: number | null;
  offers_made: number | null;
  accepted_offers: number | null;
  starters: number | null;
  representation_percent: number | null;
  shortlisting_percent: number | null;
  interview_percent: number | null;
  offer_acceptance_percent: number | null;
  appointment_percent: number | null;
};
export type InclusiveRecruitmentReport = Snapshot & {
  report: {
    as_of_date: string;
    threshold: number;
    scope: "all_observed_applications";
    dimensions: Array<{
      code: string;
      status: "available" | "suppressed" | "unavailable";
      message: string | null;
      groups: InclusiveRecruitmentGroup[];
    }>;
  };
};
export type Dashboard = { executive: Executive; vacancies: Vacancies; funnel: Funnel; sources: RecruitmentSources; trend: WorkforceTrendReport; ageing: VacancyAgeingReport; inclusive: InclusiveRecruitmentReport };
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
  | { kind: "data-architecture"; architecture: Architecture; metrics: MetricDefinition[] }
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

export async function workforceDownload(path: string, fileName: string, payload?: object) {
  try {
    const headers = new Headers({ Accept: XLSX_CONTENT_TYPE });
    if (payload) headers.set("Content-Type", "application/json");
    const response = await fetch(`${API}/${path}`, { headers, cache: "no-store",
      credentials: "same-origin", method: payload ? "POST" : "GET",
      body: payload ? JSON.stringify(payload) : undefined });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new WorkforceApiError(response.status, typeof data?.detail === "string" ? data.detail : "Download failed.");
    }
    if (response.headers.get("content-type") !== XLSX_CONTENT_TYPE) {
      throw new WorkforceApiError(502, "The server did not return a workbook.");
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    if (error instanceof WorkforceApiError) throw error;
    throw new WorkforceApiError(503, "The workbook could not be downloaded. Retry shortly.");
  }
}

export function workforceWrite<T>(path: string, method: "POST" | "PATCH", body: object, signal?: AbortSignal) {
  return workforceRequest<T>(path, {
    method, signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
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

export function loadFullWorkforceDataset(dataset: Dataset, key: string, mode: "controlled" | "exploratory",
  generationSeed?: number) {
  return workforceWrite<Snapshot & { reset_generation: number; replayed: boolean }>(
    "demo/seed", "POST", { ...datasetVersion(dataset), confirmed: true, idempotency_key: key,
      mode, generation_seed: generationSeed },
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
    const cutoff = filters.end ? `?as_of_date=${encodeURIComponent(filters.end)}` : "";
    const [architecture, { metrics }] = await Promise.all([
      workforceRequest<Architecture>(`architecture/layers${cutoff}`, { signal }),
      workforceRequest<{ metrics: MetricDefinition[] }>("metrics", { signal }),
    ]);
    return { ...architecture, kind: mode, architecture, metrics };
  }

  const dates = new URLSearchParams();
  if (filters.end) dates.set("as_of_date", filters.end);
  const range = new URLSearchParams(dates);
  if (filters.start) range.set("period_start", filters.start);
  const cohort = new URLSearchParams(range);
  if (filters.vacancyId) cohort.set("vacancy_id", filters.vacancyId);

  for (let attempt = 0; attempt < 2; attempt++) {
    const [executive, vacancies, funnel, sources, trend, ageing, inclusive] = await Promise.all([
      workforceRequest<Executive>(`analytics/executive?${range}`, { signal }),
      workforceRequest<Vacancies>(`analytics/vacancy-lifecycle?${dates}`, { signal }),
      workforceRequest<Funnel>(`analytics/candidate-funnel?${cohort}`, { signal }),
      workforceRequest<RecruitmentSources>(`analytics/recruitment-sources?${range}`, { signal }),
      workforceRequest<WorkforceTrendReport>(`analytics/workforce-trend?${range}`, { signal }),
      workforceRequest<VacancyAgeingReport>(`analytics/vacancy-ageing?${dates}`, { signal }),
      workforceRequest<InclusiveRecruitmentReport>("analytics/inclusive-recruitment", { signal }),
    ]);
    const dataset = executive.dataset;
    if ([vacancies, funnel, sources, trend, ageing, inclusive].every((value) =>
      sameGeneration(dataset, value.dataset) && dataset.revision === value.dataset.revision)) {
      return { kind: mode, synthetic: true, dataset, dashboard: { executive, vacancies, funnel, sources, trend, ageing, inclusive } };
    }
  }
  throw new WorkforceApiError(409, "The dataset changed while these reports loaded. Refresh the view.");
}
