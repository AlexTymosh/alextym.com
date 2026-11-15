"""Canonical definitions for the MVP Workforce analytical outputs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    code: str
    name: str
    unit: str
    formula: str
    numerator: str
    denominator: str | None
    exclusions: str
    grain: str
    source_tables: tuple[str, ...]
    caveat: str
    quality_rule: str
    version: str = "1.0"
    effective_from: str = "2026-07-01"
    owner: str = "Workforce Intelligence demo"
    refresh: str = "Computed on request from the committed dataset revision."
    target: float | None = None
    valid_dimensions: tuple[str, ...] = ("as_of_date",)
    synthetic: bool = True


CATALOGUE = {
    item.code: item
    for item in (
        MetricDefinition(
            "open_vacancies",
            "Open vacancies",
            "vacancies",
            "Count of approved requests still open",
            "Open vacancy requests",
            None,
            "Cancelled, administratively closed and fully filled requests",
            "Vacancy request at the selected date",
            ("vacancies", "starter_events"),
            "A multi-position request counts once. Partial fills can leave the request open.",
            "A fill must be linked to a valid starter.",
        ),
        MetricDefinition(
            "vacancy_wte",
            "Open vacancy WTE",
            "WTE",
            "Sum of remaining approved WTE on open requests",
            "Approved WTE less actual recruited WTE per open request",
            None,
            "Closed requests; WTE already filled by actual starters",
            "Vacancy request at the selected date",
            ("vacancies", "starter_events"),
            "Recruiting WTE and the establishment gap are distinct measures.",
            "A fill must be linked to a valid starter; remaining WTE cannot be negative.",
        ),
        MetricDefinition(
            "vacancy_rate",
            "Vacancy rate",
            "%",
            "Open vacancy WTE ÷ budgeted establishment WTE × 100",
            "Open vacancy WTE",
            "Budgeted establishment WTE",
            "Cancelled and administratively closed requests",
            "Workforce snapshot",
            ("vacancies", "starter_events", "establishment_history"),
            "The numerator represents active recruitment demand.",
            "Budgeted WTE must be positive.",
        ),
        MetricDefinition(
            "budgeted_wte",
            "Budgeted establishment",
            "WTE",
            "Sum of effective budgeted WTE",
            "Approved budgeted WTE",
            None,
            "Budget intervals outside the selected date",
            "Budget line snapshot",
            ("establishment_history",),
            "A budget line groups positions by organisation, location and role.",
            "At least one active budget line must exist.",
        ),
        MetricDefinition(
            "substantive_wte",
            "Current substantive workforce",
            "WTE",
            "Sum of effective substantive contract FTE",
            "Effective substantive FTE with an active assignment",
            None,
            "Non-substantive and non-effective contracts",
            "Employee at the selected date",
            ("employment_contracts", "organisation_assignments"),
            "FTE can change on dates after a person was recruited.",
            "Each effective contract has one applicable assignment.",
        ),
        MetricDefinition(
            "workforce_gap_wte",
            "Workforce gap",
            "WTE",
            "Budgeted establishment WTE − substantive WTE",
            "Budgeted WTE less substantive WTE",
            None,
            "Open requisitions and offer decisions do not contribute to filled WTE",
            "Workforce snapshot",
            ("establishment_history", "employment_contracts", "organisation_assignments"),
            "Positive values show a shortfall. Negative values show workforce above budget.",
            "An effective budget and workforce coverage must exist.",
        ),
        MetricDefinition(
            "new_starters",
            "New starters",
            "people",
            "Count of actual starter events in the reporting period",
            "Actual starts",
            None,
            "Accepted offers and confirmed starts without an actual start event",
            "Actual starter event",
            ("starter_events", "offers", "employment_contracts", "organisation_assignments"),
            "Counted in the period of the actual start, regardless of the application receipt period.",
            "Each start requires a valid accepted offer and effective employment.",
            valid_dimensions=("period_start", "as_of_date"),
        ),
        MetricDefinition(
            "median_time_to_hire",
            "Median time to hire",
            "days",
            "Median days from approval to offer acceptance",
            "Approval-to-acceptance durations",
            None,
            "Offers with no acceptance in the selected reporting period",
            "Accepted offer",
            ("vacancies", "offers"),
            "The selected period applies to the acceptance date.",
            "At least one accepted offer with a valid approval date must exist.",
            valid_dimensions=("period_start", "as_of_date"),
        ),
        MetricDefinition(
            "offer_acceptance_rate",
            "Offer acceptance rate",
            "%",
            "Accepted offers ÷ valid offers made × 100",
            "Offers made in the period and accepted by the cutoff",
            "Valid offers made in the period",
            "Employer withdrawals recorded by the cutoff",
            "Offer-made cohort",
            ("offers",),
            "Pending offers are in the cohort and can change the result as they resolve.",
            "The eligible cohort must be nonempty.",
            valid_dimensions=("period_start", "as_of_date"),
        ),
        MetricDefinition(
            "stage_conversion",
            "Application stage conversion",
            "%",
            "Applications reaching next stage ÷ prior stage × 100",
            "Distinct applications reaching the next stage",
            "Distinct applications reaching its preceding stage",
            "Repeated events and events outside the sequential path by cutoff",
            "Application receipt cohort",
            ("candidate_applications", "application_stage_events", "offers", "starter_events"),
            "Observed to date. Pending applications have less follow-up and may progress later.",
            "Prior stage must have at least one eligible application.",
            valid_dimensions=("period_start", "as_of_date", "vacancy_id"),
        ),
        MetricDefinition(
            "application_to_start",
            "Application-to-start conversion",
            "%",
            "Started applications ÷ eligible applications × 100",
            "Distinct cohort applications with an actual start on the sequential path",
            "Valid distinct applications received",
            "Repeated stages and starts outside the selected cohort",
            "Application receipt cohort",
            ("candidate_applications", "application_stage_events", "offers", "starter_events"),
            "Observed to date for the receipt cohort. A recent cohort has less follow-up.",
            "The eligible cohort must be nonempty.",
            valid_dimensions=("period_start", "as_of_date", "vacancy_id"),
        ),
    )
}
