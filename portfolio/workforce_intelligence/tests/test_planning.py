from datetime import date

import pytest
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import ensure_dataset
from workforce_intelligence.forecasting import (
    ActualMonth,
    fit_forecast,
    forecast_history,
    month_start,
)
from workforce_intelligence.scale_seed import FULL_SEED
from workforce_intelligence.scenarios import OpeningPosition, ScenarioInputs, project


def test_seasonal_baseline_wins_exact_seasonal_holdout_and_skips_partial_cutoff():
    start = date(2023, 1, 1)
    actuals = [
        ActualMonth(month=month_start(start, i).isoformat()[:7], value=i % 12) for i in range(36)
    ]
    result = fit_forecast(actuals, date(2026, 1, 10), 3, "new_starters")
    assert result.selected == "Seasonal naïve"
    assert result.scores[0].mae == 0
    assert result.scores[1].mae > 0
    assert result.validation_months == 12
    assert [(p.month, p.value) for p in result.projected] == [
        ("2026-02", 1),
        ("2026-03", 2),
        ("2026-04", 3),
    ]


def test_smoothing_wins_on_nonseasonal_level_change():
    start = date(2024, 1, 1)
    actuals = [
        ActualMonth(month=month_start(start, i).isoformat()[:7], value=2 if i < 12 else 20)
        for i in range(30)
    ]
    result = fit_forecast(actuals, date(2026, 6, 30), 2, "vacancy_wte")
    assert result.selected == "Simple exponential smoothing"
    assert result.scores[1].mae < result.scores[0].mae
    assert result.projected[0].value == pytest.approx(20, abs=0.01)


def test_missing_history_breaks_training_and_empty_history_is_explicit():
    actuals = [
        ActualMonth(
            month=month_start(date(2024, 1, 1), i).isoformat()[:7], value=None if i == 20 else 0
        )
        for i in range(24)
    ]
    for history, months in [(actuals, 3), ([], 0)]:
        result = fit_forecast(history, date(2025, 12, 31), 6, "new_starters")
        assert result.status == "insufficient_history"
        assert result.training_months == months
        assert not result.projected and not result.scores


def test_complete_monthly_history_uses_actual_starts_and_mature_attrition(tmp_path):
    database = Database(tmp_path / "planning.sqlite3")
    state = ensure_dataset(database, FULL_SEED)
    with database.transaction() as connection:
        report = forecast_history(connection, state, date(2026, 10, 15), "new_starters")
        attrition = forecast_history(connection, state, None, "early_attrition_12m")
        actual_count = connection.execute(
            "SELECT COUNT(*) FROM fact_new_starter WHERE started_on BETWEEN ? AND '2026-09-30'",
            (state.history_start,),
        ).fetchone()[0]
    assert len(report.history) == 35
    assert report.history[-1].month == "2026-09"
    assert sum(month.value for month in report.history) == actual_count
    assert all(month.value is None for month in attrition.history[:12])
    assert attrition.history[-1].value is not None


def test_scenario_capacity_internal_appointments_and_attrition_are_distinct():
    cutoff = date(2026, 10, 31)
    opening = OpeningPosition(vacancy_wte=2, open_positions=5, substantive_wte=15, budgeted_wte=20)
    committed = ScenarioInputs(
        approvals_per_month=0, planned_starts=4, internal_rate=1, wte_per_position=1
    )
    internal = project(opening, cutoff, 2, committed)
    assert internal.expected_starts == 2
    assert internal.months[-1].external_starts == 0
    assert internal.months[-1].workforce_gap_wte == 5
    assert internal.months[-1].vacancy_wte == 0
    assert internal.expected_time_to_fill is None

    external = project(
        opening,
        cutoff,
        2,
        committed.model_copy(update={"internal_rate": 0, "early_attrition_rate": 0}),
    )
    attrition = project(
        opening,
        cutoff,
        2,
        committed.model_copy(update={"internal_rate": 0, "early_attrition_rate": 1}),
    )
    assert external.months[-1].workforce_gap_wte == 3
    assert attrition.months[-1].workforce_gap_wte == 4


def test_checks_delay_future_cohort_fills_and_zero_acceptance_creates_no_starts():
    opening = OpeningPosition(vacancy_wte=0, open_positions=0, substantive_wte=0, budgeted_wte=None)
    cutoff = date(2026, 10, 31)
    inputs = ScenarioInputs()
    result = project(opening, cutoff, 3, inputs)
    assert result.expected_time_to_fill == 63
    assert [month.starts for month in result.months[:2]] == [0, 0]
    assert result.months[-1].starts > 0
    assert result.months[-1].workforce_gap_wte is None
    assert (
        project(
            opening, cutoff, 3, inputs.model_copy(update={"acceptance_rate": 0})
        ).expected_starts
        == 0
    )
