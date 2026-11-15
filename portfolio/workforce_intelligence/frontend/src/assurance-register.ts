/** Presentation-only rule guidance for the four server-computed quality counts.
 * This is not a second implementation of rule evaluation or KPI formulas.
 */
export const QUALITY_RULE_GUIDANCE: Record<string, {
  title: string; impact: string; investigation: string;
}> = {
  excluded_applications: {
    title: "Excluded applications",
    impact: "Application cohort, source mix and recruitment funnel may be incomplete.",
    investigation: "Review vacancy references and application receipt chronology.",
  },
  excluded_offers: {
    title: "Excluded offers",
    impact: "Offer and conversion metrics may exclude invalid offer records.",
    investigation: "Reconcile each offer to an eligible application and its dates.",
  },
  excluded_starters: {
    title: "Excluded starters",
    impact: "Actual starts, filled vacancies and staffing outcomes may omit records.",
    investigation: "Check accepted-offer linkage and effective starter employment.",
  },
  unassigned_contracts: {
    title: "Unassigned contracts",
    impact: "Substantive WTE and workforce gap may exclude effective contracts.",
    investigation: "Match each current substantive contract to an effective assignment.",
  },
};

export type SourceEntry = {
  code: string;
  item: string;
  type: "synthetic" | "public-reference" | "modelling-assumption";
  provenance: string;
  period: string;
  reference: string | null;
  verification: string;
  usedFor: string;
  limitation: string;
};

/** Publication names and URLs are specification references, not live-verified evidence. */
export const SOURCE_REGISTER: readonly SourceEntry[] = [
  {
    code: "contracts", item: "Synthetic employment and establishment",
    type: "synthetic", provenance: "Workforce demo SQLite: employment_contracts, organisation_assignments, establishment_history",
    period: "Effective-dated records within the demo history", reference: null,
    verification: "Generated and edited within the synthetic dataset",
    usedFor: "Workforce WTE, budget, gap, employee-month and retention modelling",
    limitation: "Fictional records; not a representation of NHS staffing levels",
  },
  {
    code: "recruitment", item: "Synthetic recruitment events",
    type: "synthetic", provenance: "Workforce demo SQLite: vacancies, candidate_applications, application_stage_events, offers, starter_events",
    period: "Dated records within the demo history", reference: null,
    verification: "Generated and edited within the synthetic dataset",
    usedFor: "Vacancy ageing, recruitment funnel, channels and observed cohort conversion",
    limitation: "Application-grain counts do not imply unique people; recent cohorts are immature",
  },
  {
    code: "voice", item: "Synthetic survey evidence",
    type: "synthetic", provenance: "Workforce People Voice demonstration fixture and reviewed findings",
    period: "Demonstration survey period", reference: null,
    verification: "Project-local fixture, not an official staff survey",
    usedFor: "Illustrative themes, evidence traceability and human-reviewed actions",
    limitation: "Not a valid estimate of real staff sentiment or prevalence",
  },
  {
    code: "structure", item: "Organisational model",
    type: "modelling-assumption", provenance: "Project-generated organisational units, locations, roles and budget lines",
    period: "Synthetic dataset generation", reference: null,
    verification: "Defined by the project seed and schema",
    usedFor: "Dimensional analysis and effective-dated source joins",
    limitation: "Demonstration hierarchy; not an authoritative SCAS organisation chart",
  },
  {
    code: "people-strategy", item: "SCAS People Strategy 2023–2026",
    type: "public-reference", provenance: "SCAS People Strategy 2023–2026",
    period: "2023–2026", reference: "https://www.scas.nhs.uk/wp-content/uploads/2023/05/SCAS-People-Strategy-2023-2026-web.pdf",
    verification: "URL taken from specification v1.2; not independently checked for this release",
    usedFor: "Context for KPI topics and workforce reporting priorities",
    limitation: "Not used as source values for synthetic KPI calculations",
  },
  {
    code: "annual-report", item: "SCAS Annual Report and Accounts 2025/26",
    type: "public-reference", provenance: "SCAS Annual Report and Accounts 2025/26",
    period: "2025/26", reference: "https://www.scas.nhs.uk/wp-content/uploads/2026/09/SCAS_Annual_Report_and_Accounts_2025-26.pdf",
    verification: "URL taken from specification v1.2; not independently checked for this release",
    usedFor: "Public context for scale and reporting terminology",
    limitation: "Public figures are not merged into synthetic employment records",
  },
  {
    code: "wres", item: "SCAS WRES reporting reference",
    type: "public-reference", provenance: "SCAS Workforce Race Equality Standard report link in specification v1.2",
    period: "2026 report link", reference: "https://www.scas.nhs.uk/wp-content/uploads/2026/10/WRES-Annual-Report-2026a.pdf",
    verification: "URL taken from specification v1.2; not independently checked for this release",
    usedFor: "Potential external equality benchmark context only",
    limitation: "No public WRES percentage is substituted for synthetic recruitment outcomes",
  },
] as const;
