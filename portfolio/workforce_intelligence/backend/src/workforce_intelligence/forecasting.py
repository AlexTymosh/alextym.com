"""Synthetic monthly forecasts with a genuinely out-of-sample baseline."""

import sqlite3
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import mean, median
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from workforce_intelligence.analytics import (
    ReportingWindow,
    accepted_offer_durations,
    mature_starter_outcomes,
    reporting_window,
)
from workforce_intelligence.dataset import DatasetState
from workforce_intelligence.schemas import DatasetRequest, DatasetResponse
from workforce_intelligence.workforce_trend import workforce_trend

MODEL_VERSION = "monthly-v1"
SEASON = 12
MIN_HISTORY = 18
ALPHA = 0.35
Horizon = Annotated[int, Field(strict=True, ge=1, le=12)]
ForecastMetric = Literal[
    "vacancy_wte",
    "workforce_gap_wte",
    "new_starters",
    "applications",
    "median_time_to_hire",
    "early_attrition_12m",
]


class PlanningRequest(DatasetRequest):
    as_of_date: date | None = None
    horizon: Horizon = 6
    source_revision: Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]


class ForecastRequest(PlanningRequest):
    metric: ForecastMetric


class ActualMonth(BaseModel):
    month: str
    value: float | None


class ForecastHistory(DatasetResponse):
    cutoff: date
    history: list[ActualMonth]


class ProjectedMonth(BaseModel):
    month: str
    value: float
    baseline: float


class ModelScore(BaseModel):
    model: Literal["Seasonal naïve", "Simple exponential smoothing"]
    mae: float


class ForecastResult(BaseModel):
    metric: ForecastMetric
    status: Literal["complete", "insufficient_history"]
    cutoff: date
    horizon: Horizon
    history: list[ActualMonth]
    projected: list[ProjectedMonth] = Field(default_factory=list)
    training_start: str | None = None
    training_end: str | None = None
    training_months: int
    minimum_months: int = MIN_HISTORY
    validation_months: int = 0
    selected: str | None = None
    scores: list[ModelScore] = Field(default_factory=list)


def month_start(day: date, offset: int = 0) -> date:
    index = day.year * 12 + day.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def month_end(day: date) -> date:
    return day.replace(day=monthrange(day.year, day.month)[1])


def _vacancy_wte(connection: sqlite3.Connection, start: date, end: date) -> dict[str, float]:
    rows = connection.execute(
        """
        WITH RECURSIVE months(start_day, end_day) AS (
            SELECT :start, date(:start, '+1 month', '-1 day')
            UNION ALL
            SELECT date(start_day, '+1 month'), date(start_day, '+2 months', '-1 day')
            FROM months WHERE date(start_day, '+2 months', '-1 day') <= :end
        ), starters AS MATERIALIZED (
            SELECT vacancy_id, started_on, started_fte_milli
            FROM fact_new_starter WHERE started_on <= :end
        ), open_vacancies AS (
            SELECT months.start_day, vacancy.id,
                   MAX(0, vacancy.approved_fte_milli - COALESCE(SUM(starters.started_fte_milli), 0))
                       AS open_milli
            FROM months JOIN bronze_vacancies vacancy
              ON vacancy.approved_on <= months.end_day
             AND (vacancy.closed_on IS NULL OR vacancy.closed_on > months.end_day)
            LEFT JOIN starters ON starters.vacancy_id = vacancy.id AND starters.started_on <= months.end_day
            GROUP BY months.start_day, vacancy.id
        )
        SELECT substr(start_day, 1, 7), SUM(open_milli) / 1000.0
        FROM open_vacancies GROUP BY start_day
        """,
        {"start": start.isoformat(), "end": end.isoformat()},
    )
    return {month: value for month, value in rows}


def _history(
    connection: sqlite3.Connection, window: ReportingWindow, metric: ForecastMetric
) -> list[ActualMonth]:
    trend = (
        workforce_trend(connection, window)
        if metric in ("workforce_gap_wte", "new_starters")
        else None
    )
    if trend is not None:
        return [
            ActualMonth(
                month=point.month_key,
                value=point.workforce_gap_wte
                if metric == "workforce_gap_wte"
                else point.new_starters,
            )
            for point in trend.points
            if not point.partial_period
        ]
    start = month_start(window.start, int(window.start.day != 1))
    if month_end(start) > window.end:
        return []
    durations: dict[str, list[int]] = defaultdict(list)
    matured: list[tuple[str, int]] = []
    month_counts: dict[str, int | float] = {}
    if metric == "vacancy_wte":
        month_counts = _vacancy_wte(connection, start, window.end)
    elif metric == "applications":
        month_counts = Counter(
            received_on[:7]
            for (received_on,) in connection.execute(
                "SELECT received_on FROM fact_application WHERE received_on BETWEEN ? AND ?",
                (start.isoformat(), window.end.isoformat()),
            )
        )
    elif metric == "median_time_to_hire":
        for resolved_on, days in accepted_offer_durations(connection, window):
            durations[resolved_on[:7]].append(days)
    else:
        matured = [
            (followup_end, left)
            for followup_end, left in mature_starter_outcomes(connection, window)
        ]

    values = []
    while (end := month_end(start)) <= window.end:
        month = start.isoformat()[:7]
        if metric in ("vacancy_wte", "applications"):
            value = month_counts.get(month, 0)
        elif metric == "median_time_to_hire":
            value = median(durations[month]) if durations[month] else None
        else:
            # Starters who completed 365 days of follow-up in the preceding 365 days.
            lower = (end - timedelta(days=364)).isoformat()
            upper = end.isoformat()
            outcomes = [left for followup, left in matured if lower <= followup <= upper]
            value = round(100 * mean(outcomes), 2) if len(outcomes) >= 5 else None
        values.append(ActualMonth(month=month, value=value))
        start = month_start(start, 1)
    return values


def _smoothed_level(values: list[float]) -> float:
    level = values[0]
    for value in values[1:]:
        level += ALPHA * (value - level)
    return level


def fit_forecast(
    history: list[ActualMonth], cutoff: date, horizon: int, metric: ForecastMetric
) -> ForecastResult:
    # Use the most recent uninterrupted run so a missing observation never becomes zero
    # or silently shifts the month for the seasonal comparison.
    training = history[
        max((i + 1 for i, row in enumerate(history) if row.value is None), default=0) :
    ]
    values = [row.value for row in training if row.value is not None]
    result = ForecastResult(
        metric=metric,
        status="insufficient_history",
        cutoff=cutoff,
        horizon=horizon,
        history=history,
        training_months=len(values),
        training_start=training[0].month if training else None,
        training_end=training[-1].month if training else None,
    )
    if len(values) < MIN_HISTORY:
        return result

    holdout = range(max(SEASON, len(values) - SEASON), len(values))
    seasonal_error = mean(abs(values[i] - values[i - SEASON]) for i in holdout)
    smooth_error = mean(abs(values[i] - _smoothed_level(values[:i])) for i in holdout)
    seasonal = ModelScore(model="Seasonal naïve", mae=round(seasonal_error, 3))
    smoothed = ModelScore(model="Simple exponential smoothing", mae=round(smooth_error, 3))
    use_smoothing = smooth_error < seasonal_error
    level = round(_smoothed_level(values), 3)
    skipped = int(cutoff < month_end(cutoff))
    projected = []
    for ahead in range(horizon):
        baseline = values[-SEASON + (ahead + skipped) % SEASON]
        projected.append(
            ProjectedMonth(
                month=month_start(cutoff, ahead + 1).isoformat()[:7],
                value=level if use_smoothing else baseline,
                baseline=baseline,
            )
        )
    return result.model_copy(
        update={
            "status": "complete",
            "projected": projected,
            "validation_months": len(holdout),
            "selected": smoothed.model if use_smoothing else seasonal.model,
            "scores": [seasonal, smoothed],
        }
    )


def forecast(
    connection: sqlite3.Connection, state: DatasetState, command: ForecastRequest
) -> ForecastResult:
    actual = forecast_history(connection, state, command.as_of_date, command.metric)
    return fit_forecast(actual.history, actual.cutoff, command.horizon, command.metric)


def forecast_history(
    connection: sqlite3.Connection, state: DatasetState, cutoff: date | None, metric: ForecastMetric
) -> ForecastHistory:
    window = reporting_window(state, cutoff, date.fromisoformat(state.history_start))
    return ForecastHistory(
        dataset=state, cutoff=window.end, history=_history(connection, window, metric)
    )
