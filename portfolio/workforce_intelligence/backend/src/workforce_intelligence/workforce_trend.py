"""Revision-current Workforce monthly movement and WTE history.

The report uses one month-end *snapshot* per observed month and event counts
within the selected reporting window. A partial opening or closing month is
explicitly labelled rather than silently presented as a full month.
"""

import sqlite3
from dataclasses import dataclass

from workforce_intelligence.analytics import ReportingWindow


@dataclass(frozen=True)
class WorkforceTrendPoint:
    month_key: str
    as_of_date: str
    partial_period: bool
    budgeted_wte: float | None
    substantive_wte: float
    workforce_gap_wte: float | None
    new_starters: int
    leavers: int


@dataclass(frozen=True)
class WorkforceTrend:
    window: ReportingWindow
    points: list[WorkforceTrendPoint]


# No fan-out between establishment, contracts and events: each subquery has
# an independent grain and is evaluated at the same effective cutoff.
_TREND_SQL = """
WITH RECURSIVE months(month_start) AS (
    SELECT date(:start, 'start of month')
    UNION ALL
    SELECT date(month_start, '+1 month')
    FROM months
    WHERE date(month_start, '+1 month') <= date(:cutoff, 'start of month')
), cutoffs AS (
    SELECT month_start, substr(month_start, 1, 7) AS month_key,
           MIN(date(month_start, '+1 month', '-1 day'), :cutoff) AS snapshot_day,
           (month_start < :start OR date(month_start, '+1 month', '-1 day') > :cutoff)
             AS partial_period
    FROM months
)
SELECT cutoffs.month_key, cutoffs.snapshot_day, cutoffs.partial_period,
       (SELECT SUM(budget_fte_milli)
        FROM bronze_establishment_history budget
        WHERE budget.valid_from <= cutoffs.snapshot_day
          AND (budget.valid_to IS NULL OR budget.valid_to > cutoffs.snapshot_day)) AS budget_milli,
       (SELECT COALESCE(SUM(contracted_fte_milli), 0)
        FROM fact_employment_interval employment
        WHERE employment.valid_from <= cutoffs.snapshot_day
          AND (employment.valid_to IS NULL OR employment.valid_to > cutoffs.snapshot_day))
          AS substantive_milli,
       (SELECT COUNT(*) FROM fact_new_starter starter
        WHERE starter.started_on BETWEEN MAX(cutoffs.month_start, :start)
                                  AND cutoffs.snapshot_day) AS starters,
       (SELECT COUNT(*) FROM fact_leaver leaver
        WHERE leaver.leaving_date BETWEEN MAX(cutoffs.month_start, :start)
                                      AND cutoffs.snapshot_day) AS leavers
FROM cutoffs ORDER BY cutoffs.month_start
"""


def workforce_trend(connection: sqlite3.Connection, window: ReportingWindow) -> WorkforceTrend:
    """Read source-aligned WTE snapshots and dated events without stale caches."""
    points: list[WorkforceTrendPoint] = []
    for row in connection.execute(
        _TREND_SQL, {"start": window.start.isoformat(), "cutoff": window.end.isoformat()}
    ):
        budget = row["budget_milli"]
        substantive = row["substantive_milli"]
        points.append(
            WorkforceTrendPoint(
                month_key=row["month_key"],
                as_of_date=row["snapshot_day"],
                partial_period=bool(row["partial_period"]),
                budgeted_wte=budget / 1000 if budget is not None else None,
                substantive_wte=substantive / 1000,
                workforce_gap_wte=(budget - substantive) / 1000 if budget is not None else None,
                new_starters=row["starters"],
                leavers=row["leavers"],
            )
        )
    return WorkforceTrend(window=window, points=points)
