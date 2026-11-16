import { datasetVersion, sameGeneration, WorkforceApiError, type Dataset } from "./data-api";

export const FORECAST_METRICS = {
  vacancy_wte: { label: "Open vacancy WTE", unit: "WTE", method: "Approved open WTE less recorded starts at month end." },
  workforce_gap_wte: { label: "Workforce gap", unit: "WTE", method: "Effective establishment less substantive contract WTE at month end." },
  new_starters: { label: "Recruitment starts", unit: "starts", method: "Actual recorded starts in each month." },
  applications: { label: "Applications received", unit: "applications", method: "Distinct conformed applications received in each month." },
  median_time_to_hire: { label: "Median time to hire", unit: "days", method: "Days from vacancy approval to offer acceptance, grouped by acceptance month." },
  early_attrition_12m: { label: "Early attrition", unit: "%", method: "Early leavers among starters who completed 365 days of follow-up in the preceding year. At least five eligible starters per point." },
} as const;

export type ForecastMetric = keyof typeof FORECAST_METRICS;
export type ActualMonth = { month: string; value: number | null };
export type ProjectedMonth = { month: string; value: number; baseline: number };
export type ForecastHistory = { dataset: Dataset; history: ActualMonth[] };
export type ForecastRun = {
  dataset: Dataset; model_version: string; run_id: string;
  forecast: {
    status: "insufficient_history" | "complete"; history: ActualMonth[]; projected: ProjectedMonth[];
    training_start: string | null; training_end: string | null; training_months: number;
    minimum_months: number; validation_months: number; selected: string | null;
    scores: Array<{ model: string; mae: number }>; horizon: number;
  };
};

export type ScenarioInputs = {
  approvals_per_month: number; applicants_per_position: number;
  shortlist_rate: number; interview_rate: number; offer_rate: number; acceptance_rate: number;
  checks_pass_rate: number; days_to_offer: number; days_for_checks: number; days_to_start: number;
  planned_starts: number; internal_rate: number; early_attrition_rate: number; wte_per_position: number;
};
export type ScenarioMonth = {
  month: string; starts: number; external_starts: number; vacancy_wte: number; workforce_gap_wte: number | null;
};
export type ScenarioProjection = {
  expected_starts: number; expected_time_to_fill: number | null;
  modelled_planned_starts: number; months: ScenarioMonth[];
};
export type ScenarioRun = {
  dataset: Dataset; model_version: string; run_id: string;
  evaluation: {
    cutoff: string;
    opening: { vacancy_wte: number; open_positions: number; substantive_wte: number; budgeted_wte: number | null };
    inputs: ScenarioInputs; baseline_inputs: ScenarioInputs; scenario: ScenarioProjection; baseline: ScenarioProjection;
  };
};

export function planningPayload(dataset: Dataset, cutoff: string, horizon: number) {
  return { ...datasetVersion(dataset), source_revision: dataset.revision, as_of_date: cutoff, horizon };
}

export function checkPlanningSnapshot(expected: Dataset, actual: Dataset) {
  if (!sameGeneration(expected, actual) || expected.revision !== actual.revision) {
    throw new WorkforceApiError(409, "Source data changed. Refresh data and run again.");
  }
}
