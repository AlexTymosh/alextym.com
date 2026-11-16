import { workforceRequest, type Snapshot } from "./data-api";

export type Question = {
  code: string; prompt: string; kind: "comment" | "rating"; scale_max?: 5 | 7 | null;
};

export type Campaign = {
  survey_id: string; title: string; period_start: string; period_end: string; audience: string;
  organisation_id: string | null; series: string; anonymity_min: number; eligible: number; invited: number;
  generated_at: string | null; generation_seed: number | null; generation_mode: string | null;
  responses: number; analysable: number; taxonomy_version: string; questions: Question[];
};

export type VoiceWorkspace = Snapshot & {
  campaigns: Campaign[];
  units: { id: string; label: string }[];
  bank: Question[];
  dimensions: Record<string, string>;
  weighting_dimensions: string[];
  themes: Record<string, string>;
  series: Record<string, string>;
};
export type CampaignResponse = Snapshot & { campaign: Campaign };

export const loadVoice = (signal?: AbortSignal) => workforceRequest<VoiceWorkspace>("surveys", { signal });

type Estimate = {
  status: "available" | "suppressed"; responses: number | null; analysable: number | null;
  unweighted: number | null; weighted: number | null; effective_sample: number | null;
};
export type ReviewPriority = {
  version: string; score: number; components: Record<string, number>; weights: Record<string, number>;
  priority_human_review: boolean; trend_available: boolean; segment_available: boolean;
};
export type VoiceAnalytics = Estimate & {
  minimum: number; segments_suppressed: boolean; theme: string; dimension: string;
  weighting: {
    status: string; version: string; dimension: string; trim_min: number; trim_max: number;
    source: string; population_revision: number | null;
    groups: { category: string; eligible: number; weight: number }[];
  };
  segments: (Estimate & { category: string; eligible: number; invited: number; responded: number; response_rate: number;
    difference_pp: number | null; prevalence_ratio: number | null; trend_pp: number | null })[];
  theme_frequencies: (Estimate & { theme: string; label: string; mentions: number })[];
  trend_pp: number | null; comparison_survey_id: string | null;
  nonresponse_rate: number | null; item_nonresponse_rate: number | null;
  ratings: { question: string; scale_max: number; mean: number | null; answered: number | null }[];
  triangulation: { indicator: string; eligible: number; count: number; percent: number; relation: string }[];
  priority: ReviewPriority | null;
  requires_human_attention: boolean;
};

export type VoiceRun = {
  id: string; mode: "ai" | "demo"; status: "running" | "ready" | "failed"; label: string;
  summary?: string; provider: string; model: string; sample_size: number; started_at: string; completed_at: string | null;
  failure: string | null; taxonomy_version: string; prompt_version: string; input_hash: string; supersedes: string | null;
};
export type Signal = {
  id: string; state: "awaiting_review" | "confirmed" | "amended" | "rejected" | "published";
  theme_code: string | null; theme: string; subtheme: string | null;
  classification: string | null; severity: string | null; summary: string | null;
  unique_responses: number | null; prevalence: number | null; publication_eligible: boolean;
  evidence: { response_id: string; excerpt: string }[];
  priority: ReviewPriority | null; urgent: boolean;
  original_classification: string | null; published_on: string | null;
  review_history: { action: string; rationale: string; actor: string; occurred_at: string }[];
};
export type VoiceAction = {
  id: string; signal_id: string; title: string; assigned_team: string; status: string; due_on: string; baseline: string;
  target: string; expected_benefit: string; notes: string | null; closure_evidence: string | null; created_on: string;
};
export type VoiceReview = Snapshot & {
  runs: VoiceRun[]; selected_run: VoiceRun | null; signals: Signal[]; actions: VoiceAction[]; teams: string[];
};
