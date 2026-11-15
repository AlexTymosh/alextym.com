"""Canonical Gold reports computed over committed Bronze and Silver views."""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Literal

from workforce_intelligence.dataset import DatasetState, InvalidOperation, operation_date
from workforce_intelligence.metric_catalogue import CATALOGUE, MetricDefinition
from workforce_intelligence.recruitment import OPEN_STATUSES, vacancy_snapshots

APPLICATION_STAGES = (
    "received",
    "screened",
    "shortlisted",
    "interviewed",
    "conditional_offer",
    "offer_accepted",
    "checks_completed",
    "start_confirmed",
    "started",
    "probation_completed",
)


@dataclass(frozen=True)
class ReportingWindow:
    start: date
    end: date


@dataclass(frozen=True)
class Observation:
    value: float | None
    numerator: float | None = None
    denominator: float | None = None
    sample_size: int | None = None
    status: Literal["available", "unavailable"] = "available"
    reason: str | None = None


@dataclass(frozen=True)
class MetricComparison:
    definition: MetricDefinition
    current: Observation
    previous: Observation
    direction: Literal["up", "down", "flat", "unavailable"]


@dataclass(frozen=True)
class ExecutiveMetrics:
    metrics: list[MetricComparison]
    current_window: ReportingWindow
    previous_window: ReportingWindow | None


@dataclass(frozen=True)
class FunnelStage:
    stage: str
    application_count: int
    conversion_from_previous: Observation | None
    median_days_from_previous: Observation | None


@dataclass(frozen=True)
class ApplicationFunnel:
    window: ReportingWindow
    vacancy_id: str | None
    stages: list[FunnelStage]
    application_to_start: Observation
    grain: str = "distinct_application"


def reporting_window(
    state: DatasetState, as_of: date | None, start: date | None
) -> ReportingWindow:
    through = as_of or date.fromisoformat(state.as_of_date)
    operation_date(state, through)
    earliest = date.fromisoformat(state.history_start)
    begin = start or max(through.replace(day=1), earliest)
    if not earliest <= begin <= through:
        raise InvalidOperation(
            "Period start must be within the observed period and on or before the cutoff."
        )
    return ReportingWindow(begin, through)


def _unavailable(
    reason: str,
    *,
    numerator: float | None = None,
    denominator: float | None = None,
    sample_size: int | None = None,
) -> Observation:
    return Observation(None, numerator, denominator, sample_size, "unavailable", reason)


def _rate(numerator: float, denominator: float) -> Observation:
    if denominator <= 0:
        return _unavailable(
            "No eligible denominator in the selected window.",
            numerator=numerator,
            denominator=denominator,
        )
    return Observation(round(numerator * 100 / denominator, 2), numerator, denominator)


def _median(durations: list[int]) -> Observation:
    if not durations:
        return _unavailable(
            "No eligible completed intervals in the selected window.", sample_size=0
        )
    return Observation(median(durations), sample_size=len(durations))


def _observed_conversion(advanced: int, eligible: int, observed_before_cutoff: int) -> Observation:
    if eligible and not advanced and not observed_before_cutoff:
        return _unavailable(
            "All eligible applications reached the prior stage on the cutoff date.",
            numerator=advanced,
            denominator=eligible,
        )
    return _rate(advanced, eligible)


def _executive(connection: sqlite3.Connection, window: ReportingWindow) -> dict[str, Observation]:
    start, cutoff = window.start.isoformat(), window.end.isoformat()
    budget_milli, substantive_milli = connection.execute(
        """
        SELECT
          (SELECT SUM(budget_fte_milli) FROM bronze_establishment_history
           WHERE valid_from <= :date AND (valid_to IS NULL OR valid_to > :date)),
          (SELECT COALESCE(SUM(contracted_fte_milli), 0) FROM silver_substantive_employment
           WHERE valid_from <= :date AND (valid_to IS NULL OR valid_to > :date))
        """,
        {"date": cutoff},
    ).fetchone()
    budget = budget_milli / 1000 if budget_milli is not None else 0
    substantive = substantive_milli / 1000
    open_vacancies = [v for v in vacancy_snapshots(connection, cutoff) if v.status in OPEN_STATUSES]
    open_wte = round(sum(v.open_wte for v in open_vacancies), 3)
    starters = connection.execute(
        "SELECT COUNT(*) FROM silver_starters WHERE started_on BETWEEN ? AND ?", (start, cutoff)
    ).fetchone()[0]
    durations = [
        row[0]
        for row in connection.execute(
            """
        SELECT CAST(julianday(offer.resolved_on) - julianday(vacancy.approved_on) AS INTEGER)
        FROM silver_offers AS offer JOIN bronze_vacancies AS vacancy ON vacancy.id = offer.vacancy_id
        WHERE offer.outcome = 'accepted' AND offer.resolved_on BETWEEN ? AND ?
        """,
            (start, cutoff),
        )
    ]
    offers, accepted = connection.execute(
        """
        SELECT COUNT(*), COUNT(CASE WHEN outcome = 'accepted' AND resolved_on <= :cutoff THEN 1 END)
        FROM silver_offers WHERE offered_on BETWEEN :start AND :cutoff
        AND (outcome IS NULL OR outcome <> 'withdrawn' OR resolved_on > :cutoff)
        """,
        {"start": start, "cutoff": cutoff},
    ).fetchone()
    missing_budget = _unavailable("No effective budget for the selected date.")
    gap = (budget_milli - substantive_milli) / 1000 if budget_milli is not None else None
    return {
        "open_vacancies": Observation(len(open_vacancies), len(open_vacancies)),
        "vacancy_wte": Observation(open_wte, open_wte),
        "vacancy_rate": _rate(open_wte, budget),
        "budgeted_wte": Observation(budget, budget) if budget_milli is not None else missing_budget,
        "substantive_wte": Observation(substantive, substantive),
        "workforce_gap_wte": Observation(gap, gap) if gap is not None else missing_budget,
        "new_starters": Observation(starters, starters),
        "median_time_to_hire": _median(durations),
        "offer_acceptance_rate": _rate(accepted, offers),
    }


def executive_metrics(
    connection: sqlite3.Connection, state: DatasetState, window: ReportingWindow
) -> ExecutiveMetrics:
    prior_end = window.start - timedelta(days=1)
    prior_start = prior_end - (window.end - window.start)
    previous_window = (
        ReportingWindow(prior_start, prior_end)
        if prior_start >= date.fromisoformat(state.history_start)
        else None
    )
    previous = _executive(connection, previous_window) if previous_window else {}
    comparisons = []
    for code, current in _executive(connection, window).items():
        old = previous.get(code) or _unavailable(
            "The preceding window falls outside the observed period."
        )
        direction: Literal["up", "down", "flat", "unavailable"] = "unavailable"
        if current.value is not None and old.value is not None:
            direction = (
                "up"
                if current.value > old.value
                else "down"
                if current.value < old.value
                else "flat"
            )
        comparisons.append(MetricComparison(CATALOGUE[code], current, old, direction))
    return ExecutiveMetrics(comparisons, window, previous_window)


def application_funnel(
    connection: sqlite3.Connection, window: ReportingWindow, vacancy_id: str | None
) -> ApplicationFunnel:
    events: dict[str, dict[str, list[date]]] = defaultdict(lambda: defaultdict(list))
    for row in connection.execute(
        """
        SELECT event.application_id, event.stage_code, event.occurred_on FROM silver_application_events AS event
        JOIN silver_applications AS app ON app.id = event.application_id
        WHERE app.received_on BETWEEN :start AND :cutoff AND event.occurred_on <= :cutoff
          AND (:vacancy IS NULL OR app.vacancy_id = :vacancy)
        ORDER BY event.occurred_on
        """,
        {
            "start": window.start.isoformat(),
            "cutoff": window.end.isoformat(),
            "vacancy": vacancy_id,
        },
    ):
        events[row["application_id"]][row["stage_code"]].append(
            date.fromisoformat(row["occurred_on"])
        )

    counts = dict.fromkeys(APPLICATION_STAGES, 0)
    reached_before_cutoff = dict.fromkeys(APPLICATION_STAGES, 0)
    completed_durations = {stage: [] for stage in APPLICATION_STAGES}
    for by_stage in events.values():
        prior_date = window.start
        for index, stage in enumerate(APPLICATION_STAGES):
            reached = next((day for day in by_stage.get(stage, ()) if day >= prior_date), None)
            if reached is None:
                break
            counts[stage] += 1
            reached_before_cutoff[stage] += int(reached < window.end)
            if index:
                completed_durations[stage].append((reached - prior_date).days)
            prior_date = reached

    stages = [FunnelStage("received", counts["received"], None, None)]
    for previous, stage in zip(APPLICATION_STAGES, APPLICATION_STAGES[1:]):
        stages.append(
            FunnelStage(
                stage,
                counts[stage],
                _observed_conversion(
                    counts[stage], counts[previous], reached_before_cutoff[previous]
                ),
                _median(completed_durations[stage]),
            )
        )
    return ApplicationFunnel(
        window,
        vacancy_id,
        stages,
        _observed_conversion(
            counts["started"], counts["received"], reached_before_cutoff["received"]
        ),
    )


def quality_checks(connection: sqlite3.Connection, as_of: str) -> dict[str, int]:
    return dict(
        connection.execute(
            """
        SELECT
          (SELECT COUNT(*) FROM bronze_candidate_applications WHERE received_on <= :day) -
          (SELECT COUNT(*) FROM silver_applications WHERE received_on <= :day) AS excluded_applications,
          (SELECT COUNT(*) FROM bronze_offers WHERE offered_on <= :day) -
          (SELECT COUNT(*) FROM silver_offers WHERE offered_on <= :day) AS excluded_offers,
          (SELECT COUNT(*) FROM bronze_starter_events WHERE started_on <= :day) -
          (SELECT COUNT(*) FROM silver_starters WHERE started_on <= :day) AS excluded_starters,
          (SELECT COUNT(*) FROM bronze_employment_contracts
           WHERE is_substantive = 1 AND valid_from <= :day AND (valid_to IS NULL OR valid_to > :day)) -
          (SELECT COUNT(*) FROM silver_substantive_employment
           WHERE valid_from <= :day AND (valid_to IS NULL OR valid_to > :day)) AS unassigned_contracts
        """,
            {"day": as_of},
        ).fetchone()
    )
