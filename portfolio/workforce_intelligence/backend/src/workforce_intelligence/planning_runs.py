"""Snapshot-pinned, idempotent storage for the demonstration planning models."""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import Conflict, DatasetState, RecordNotFound, current_dataset
from workforce_intelligence.forecasting import (
    MODEL_VERSION,
    ForecastRequest,
    ForecastResult,
    PlanningRequest,
    forecast,
)
from workforce_intelligence.scenarios import (
    SCENARIO_VERSION,
    ScenarioRequest,
    ScenarioResult,
    evaluate_scenario,
)
from workforce_intelligence.schemas import DatasetResponse

if TYPE_CHECKING:
    from workforce_intelligence.dataset import AuditActor

logger = logging.getLogger(__name__)


class ForecastRun(DatasetResponse):
    run_id: UUID
    model_version: Literal["monthly-v1"] = MODEL_VERSION
    forecast: ForecastResult


class ScenarioRun(DatasetResponse):
    run_id: UUID
    model_version: Literal["recruitment-flow-v1"] = SCENARIO_VERSION
    evaluation: ScenarioResult


def _save(
    database: Database,
    command: ForecastRequest | ScenarioRequest,
    run: ForecastRun | ScenarioRun,
    actor: AuditActor,
) -> None:
    forecast_run = isinstance(run, ForecastRun)
    kind = "forecast" if forecast_run else "scenario"
    status = run.forecast.status if forecast_run else "complete"
    cutoff = run.forecast.cutoff if forecast_run else run.evaluation.cutoff
    with database.transaction(write=True) as connection:
        state = _source_state(connection, command)
        persisted = (
            connection.execute(
                """
            INSERT INTO forecast_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO NOTHING
            """,
                (
                    str(run.run_id),
                    kind,
                    run.model_version,
                    state.dataset_id,
                    state.dataset_generation,
                    state.revision,
                    cutoff.isoformat(),
                    status,
                    command.model_dump_json(),
                    run.model_dump_json(exclude={"forecast": {"projected"}}),
                    datetime.now(UTC).isoformat(),
                ),
            ).rowcount
            == 1
        )
        if persisted and forecast_run:
            connection.executemany(
                "INSERT INTO forecast_results VALUES (?, ?, ?, ?)",
                [(str(run.run_id), p.month, p.value, p.baseline) for p in run.forecast.projected],
            )
    logger.info(
        "Workforce %s run %s status=%s model=%s replayed=%s request_id=%s",
        kind,
        run.run_id,
        status,
        run.model_version,
        not persisted,
        actor.correlation_id,
    )


def _source_state(connection: sqlite3.Connection, command: PlanningRequest) -> DatasetState:
    state = current_dataset(connection, command.expected_version())
    if state.revision != command.source_revision:
        raise Conflict("Source data changed. Refresh the workspace and run again.")
    return state


def _run_id(version: str, command: PlanningRequest) -> UUID:
    return uuid5(NAMESPACE_URL, f"workforce:{version}:{command.model_dump_json()}")


def run_forecast(database: Database, command: ForecastRequest, actor: AuditActor) -> ForecastRun:
    with database.transaction() as connection:
        state = _source_state(connection, command)
        projected = forecast(connection, state, command)
    run = ForecastRun(run_id=_run_id(MODEL_VERSION, command), dataset=state, forecast=projected)
    _save(database, command, run, actor)
    return run


def run_scenario(database: Database, command: ScenarioRequest, actor: AuditActor) -> ScenarioRun:
    with database.transaction() as connection:
        state = _source_state(connection, command)
        evaluation = evaluate_scenario(connection, state, command)
    run = ScenarioRun(
        run_id=_run_id(SCENARIO_VERSION, command), dataset=state, evaluation=evaluation
    )
    _save(database, command, run, actor)
    return run


def read_scenario(database: Database, run_id: UUID) -> ScenarioRun:
    with database.transaction() as connection:
        state = current_dataset(connection)
        row = connection.execute(
            """
            SELECT result FROM forecast_runs
            WHERE id = ? AND kind = 'scenario' AND dataset_id = ? AND dataset_generation = ?
            """,
            (str(run_id), state.dataset_id, state.dataset_generation),
        ).fetchone()
        if row is None:
            raise RecordNotFound("Scenario unavailable for the current dataset.")
        return ScenarioRun.model_validate_json(row["result"])
