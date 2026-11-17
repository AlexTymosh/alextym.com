"""Whitelisted, point-in-time examples of the Workforce analytical layers."""

import sqlite3
from datetime import date
from typing import Literal

from pydantic import BaseModel

from workforce_intelligence.analytics import ReportingWindow
from workforce_intelligence.schemas import QualityResponse
from workforce_intelligence.workforce_trend import workforce_trend

Layer = Literal["operational", "bronze", "silver", "gold"]


class LayerExample(BaseModel):
    code: Layer
    relation: str
    values: dict[str, str | int | float | None]


class ArchitectureResponse(QualityResponse):
    layers: list[LayerExample]


def layer_examples(connection: sqlite3.Connection, cutoff: date) -> list[LayerExample]:
    day = cutoff.isoformat()
    contract = connection.execute(
        """
        SELECT id AS contract_id, employee_id, valid_from, valid_to, contracted_fte_milli
        FROM employment_contracts
        WHERE is_substantive = 1 AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)
        ORDER BY employee_id, id LIMIT 1
        """,
        (day, day),
    ).fetchone()
    bronze = silver = None
    if contract is not None:
        bronze = connection.execute(
            """
            SELECT id AS contract_id, employee_id, valid_from, valid_to, contracted_fte_milli,
                   dataset_generation, source_revision
            FROM bronze_employment_contracts WHERE id = ?
            """,
            (contract["contract_id"],),
        ).fetchone()
        silver = connection.execute(
            """
            SELECT employee_id, line_id, role_id, organisation_id, valid_from, valid_to,
                   contracted_fte_milli
            FROM fact_employment_interval
            WHERE employee_id = ? AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)
            """,
            (contract["employee_id"], day, day),
        ).fetchone()
    report = workforce_trend(connection, ReportingWindow(cutoff, cutoff)).points[0]
    return [
        LayerExample(
            code="operational",
            relation="employment_contracts",
            values=dict(contract) if contract else {},
        ),
        LayerExample(
            code="bronze",
            relation="bronze_employment_contracts",
            values=dict(bronze) if bronze else {},
        ),
        LayerExample(
            code="silver",
            relation="fact_employment_interval",
            values=dict(silver) if silver else {},
        ),
        LayerExample(
            code="gold",
            relation="GET /analytics/executive",
            values={
                "as_of_date": report.as_of_date,
                "budgeted_wte": report.budgeted_wte,
                "substantive_wte": report.substantive_wte,
                "workforce_gap_wte": report.workforce_gap_wte,
            },
        ),
    ]
