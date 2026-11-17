"""Deterministic recruitment throughput and WTE stock-and-flow model."""

import sqlite3
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from workforce_intelligence.analytics import reporting_window
from workforce_intelligence.dataset import DatasetState
from workforce_intelligence.forecasting import PlanningRequest, month_start
from workforce_intelligence.recruitment import OPEN_STATUSES, vacancy_snapshots
from workforce_intelligence.workforce_trend import workforce_trend

Rate = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
Days = Annotated[int, Field(strict=True, ge=0, le=180)]
SCENARIO_VERSION = "recruitment-flow-v1"


class ScenarioInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approvals_per_month: Annotated[int, Field(strict=True, ge=0, le=500)] = 8
    applicants_per_position: Annotated[
        float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)
    ] = 8
    shortlist_rate: Rate = 0.5
    interview_rate: Rate = 0.75
    offer_rate: Rate = 0.45
    acceptance_rate: Rate = 0.8
    checks_pass_rate: Rate = 0.9
    days_to_offer: Days = 28
    days_for_checks: Days = 21
    days_to_start: Days = 14
    planned_starts: Annotated[int, Field(strict=True, ge=0, le=5000)] = 0
    internal_rate: Rate = 0.15
    early_attrition_rate: Rate = 0.12
    wte_per_position: Annotated[float, Field(strict=True, ge=0.1, le=1, allow_inf_nan=False)] = 0.8


class ScenarioRequest(PlanningRequest):
    inputs: ScenarioInputs


class OpeningPosition(BaseModel):
    vacancy_wte: float
    open_positions: int
    substantive_wte: float
    budgeted_wte: float | None


class ScenarioMonth(BaseModel):
    month: str
    starts: float
    external_starts: float
    vacancy_wte: float
    workforce_gap_wte: float | None


class ScenarioProjection(BaseModel):
    expected_starts: float
    expected_time_to_fill: int | None
    modelled_planned_starts: float
    months: list[ScenarioMonth]


class ScenarioResult(BaseModel):
    cutoff: date
    opening: OpeningPosition
    inputs: ScenarioInputs
    baseline_inputs: ScenarioInputs
    scenario: ScenarioProjection
    baseline: ScenarioProjection


def project(
    opening: OpeningPosition, cutoff: date, horizon: int, inputs: ScenarioInputs
) -> ScenarioProjection:
    delay = inputs.days_to_offer + inputs.days_for_checks + inputs.days_to_start
    lag = max(0, (delay - 1) // 30)
    fills_per_cohort = inputs.approvals_per_month * min(
        1,
        inputs.applicants_per_position
        * inputs.shortlist_rate
        * inputs.interview_rate
        * inputs.offer_rate
        * inputs.acceptance_rate
        * inputs.checks_pass_rate,
    )
    planned = min(
        inputs.planned_starts, opening.open_positions, opening.vacancy_wte / inputs.wte_per_position
    )
    monthly_planned = planned / horizon
    vacancy = opening.vacancy_wte
    new_external_wte = 0.0
    total_starts = 0.0
    monthly_retention = (1 - inputs.early_attrition_rate) ** (1 / 12)
    months = []
    for i in range(horizon):
        starts = monthly_planned + (fills_per_cohort if i >= lag else 0)
        external = starts * (1 - inputs.internal_rate)
        vacancy += (inputs.approvals_per_month - starts) * inputs.wte_per_position
        new_external_wte = new_external_wte * monthly_retention + external * inputs.wte_per_position
        gap = (
            opening.budgeted_wte - opening.substantive_wte - new_external_wte
            if opening.budgeted_wte is not None
            else None
        )
        total_starts += starts
        months.append(
            ScenarioMonth(
                month=month_start(cutoff, i + 1).isoformat()[:7],
                starts=round(starts, 3),
                external_starts=round(external, 3),
                vacancy_wte=round(max(0, vacancy), 3),
                workforce_gap_wte=round(gap, 3) if gap is not None else None,
            )
        )
    return ScenarioProjection(
        expected_starts=round(total_starts, 3),
        expected_time_to_fill=delay if fills_per_cohort else None,
        modelled_planned_starts=round(planned, 3),
        months=months,
    )


def evaluate_scenario(
    connection: sqlite3.Connection, state: DatasetState, command: ScenarioRequest
) -> ScenarioResult:
    window = reporting_window(state, command.as_of_date, command.as_of_date)
    cutoff = window.end
    cutoff_snapshot = workforce_trend(connection, window).points[-1]
    open_vacancies = [
        vacancy
        for vacancy in vacancy_snapshots(connection, cutoff.isoformat())
        if vacancy.status in OPEN_STATUSES
    ]
    opening = OpeningPosition(
        vacancy_wte=round(sum(v.open_wte for v in open_vacancies), 3),
        open_positions=sum(
            max(0, v.approved_positions - v.filled_positions) for v in open_vacancies
        ),
        substantive_wte=cutoff_snapshot.substantive_wte,
        budgeted_wte=cutoff_snapshot.budgeted_wte,
    )
    baseline = ScenarioInputs()
    return ScenarioResult(
        cutoff=cutoff,
        opening=opening,
        inputs=command.inputs,
        baseline_inputs=baseline,
        scenario=project(opening, cutoff, command.horizon, command.inputs),
        baseline=project(opening, cutoff, command.horizon, baseline),
    )
