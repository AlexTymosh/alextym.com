"""Project-owned HTTP router. Host applies shared Firebase grant dependency.

This package must not import website security implementations or other projects.
Every project route is mounted with `require_workforce_member` by the host.
"""

import sqlite3
from collections import Counter
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from workforce_intelligence.analytics import (
    application_funnel,
    executive_metrics,
    quality_checks,
    reporting_window,
)
from workforce_intelligence.contracts import change_fte, employees_at
from workforce_intelligence.database import DatabaseUnavailable
from workforce_intelligence.dataset import DatasetState, current_dataset, reset_dataset
from workforce_intelligence.http import Db, Member, WorkforceRoute, audit_actor
from workforce_intelligence.metric_catalogue import CATALOGUE
from workforce_intelligence.recruitment import cancel_vacancy, record_start, vacancy_snapshots
from workforce_intelligence.schemas import (
    ActualStart,
    CatalogueResponse,
    DatasetResponse,
    EmployeePage,
    EmployeeSummary,
    EntityId,
    ErrorDetail,
    ExecutiveResponse,
    FteChange,
    FunnelResponse,
    InsightQuery,
    InsightResponse,
    MutationResponse,
    QualityResponse,
    ResetRequest,
    ResetResponse,
    StarterResponse,
    SurveyReportResponse,
    VacancyCancellation,
    VacancyLifecycle,
)
from workforce_intelligence.seed import INTERVIEW_SEED
from workforce_intelligence.survey_fixture import ANALYSIS_ID
from workforce_intelligence.surveys import read_survey_report

router = APIRouter(
    prefix="/workforce",
    tags=["Workforce Intelligence"],
    route_class=WorkforceRoute,
    dependencies=[Depends(audit_actor)],
    responses={422: {"model": ErrorDetail, "description": "Invalid Workforce input"}},
)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100_000)]
PathId = Annotated[EntityId, Path()]


@router.get("/status", include_in_schema=False)
def workforce_status() -> dict[str, bool | str]:
    return {"service": "workforce", "available": True}


@router.get("/demo/status")
def demo_status(database: Db) -> DatasetResponse:
    with database.transaction() as connection:
        return DatasetResponse(dataset=current_dataset(connection))


@router.get("/employees")
def employees(
    database: Db, as_of_date: date | None = None, limit: Limit = 25, offset: Offset = 0
) -> EmployeePage:
    with database.transaction() as connection:
        state = current_dataset(connection)
        cutoff = reporting_window(state, as_of_date, None).end.isoformat()
        rows = employees_at(connection, cutoff, limit + 1, offset)
        return EmployeePage(
            dataset=state,
            as_of_date=cutoff,
            items=[EmployeeSummary(**dict(row)) for row in rows[:limit]],
            next_offset=offset + limit if len(rows) > limit else None,
        )


@router.patch("/employees/{employee_id}/contracts")
def edit_fte(
    employee_id: PathId, command: FteChange, database: Db, actor: Member
) -> MutationResponse:
    state, version = change_fte(
        database,
        employee_id=employee_id,
        record_version=command.record_version,
        effective_from=command.effective_from,
        fte_milli=int(command.contracted_fte * 1000),
        expected=command.expected_version(),
        actor=actor,
    )
    return MutationResponse(dataset=state, record_version=version)


@router.get("/analytics/vacancy-lifecycle")
@router.get("/vacancies")
def vacancies(
    database: Db, as_of_date: date | None = None, limit: Limit = 25, offset: Offset = 0
) -> VacancyLifecycle:
    with database.transaction() as connection:
        state = current_dataset(connection)
        cutoff = reporting_window(state, as_of_date, None).end.isoformat()
        rows = vacancy_snapshots(connection, cutoff)
        return VacancyLifecycle(
            dataset=state,
            as_of_date=cutoff,
            status_counts=dict(Counter(row.status for row in rows)),
            items=rows[offset : offset + limit],
            next_offset=offset + limit if len(rows) > offset + limit else None,
        )


@router.post("/vacancies/{vacancy_id}/cancel")
def cancel(
    vacancy_id: PathId, command: VacancyCancellation, database: Db, actor: Member
) -> MutationResponse:
    state, version = cancel_vacancy(
        database,
        vacancy_id=vacancy_id,
        record_version=command.record_version,
        cancelled_on=command.cancelled_on,
        expected=command.expected_version(),
        actor=actor,
    )
    return MutationResponse(dataset=state, record_version=version)


@router.post("/starters", status_code=201)
def add_starter(command: ActualStart, database: Db, actor: Member) -> StarterResponse:
    state, version, employee_id = record_start(
        database,
        offer_id=command.offer_id,
        record_version=command.record_version,
        started_on=command.started_on,
        fte_milli=int(command.contracted_fte * 1000),
        expected=command.expected_version(),
        actor=actor,
    )
    return StarterResponse(dataset=state, record_version=version, employee_id=employee_id)


def _quality(connection: sqlite3.Connection, state: DatasetState, cutoff: str) -> QualityResponse:
    issues = quality_checks(connection, cutoff)
    return QualityResponse(
        dataset=state,
        as_of_date=cutoff,
        issues=issues,
        quality_status="review_required" if any(issues.values()) else "passed",
    )


@router.get("/analytics/executive")
def executive(
    database: Db, as_of_date: date | None = None, period_start: date | None = None
) -> ExecutiveResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, as_of_date, period_start)
        quality = _quality(connection, state, window.end.isoformat())
        return ExecutiveResponse(
            **quality.model_dump(), executive=executive_metrics(connection, state, window)
        )


@router.get("/analytics/candidate-funnel")
def funnel(
    database: Db,
    as_of_date: date | None = None,
    period_start: date | None = None,
    vacancy_id: EntityId | None = None,
) -> FunnelResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, as_of_date, period_start)
        quality = _quality(connection, state, window.end.isoformat())
        return FunnelResponse(
            **quality.model_dump(), funnel=application_funnel(connection, window, vacancy_id)
        )


@router.get("/metrics")
def metric_catalogue() -> CatalogueResponse:
    return CatalogueResponse(metrics=list(CATALOGUE.values()))


@router.get("/data-quality")
def data_quality(database: Db, as_of_date: date | None = None) -> QualityResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        cutoff = reporting_window(state, as_of_date, None).end.isoformat()
        return _quality(connection, state, cutoff)


@router.post("/demo/reset")
def reset(command: ResetRequest, database: Db, actor: Member) -> ResetResponse:
    result = reset_dataset(
        database,
        INTERVIEW_SEED,
        expected=command.expected_version(),
        actor=actor,
        idempotency_key=str(command.idempotency_key),
    )
    return ResetResponse(
        dataset=result.dataset, reset_generation=result.reset_generation, replayed=result.replayed
    )


@router.get("/surveys/reports/rota-pressure")
def reviewed_report(database: Db) -> SurveyReportResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        report = read_survey_report(connection, ANALYSIS_ID)
        if report is None:
            raise DatabaseUnavailable("Controlled People Voice report is missing")
        return SurveyReportResponse(dataset=state, report=report)


@router.post("/insight-pilot/query")
def insight_pilot(query: InsightQuery, database: Db) -> InsightResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, query.as_of_date, query.period_start)
        quality = _quality(connection, state, window.end.isoformat())
        report = executive_metrics(connection, state, window)
        metric = next(item for item in report.metrics if item.definition.code == "vacancy_rate")
        return InsightResponse(
            **quality.model_dump(),
            intent=query.intent,
            window=window,
            metric=metric,
            limitation="Illustrative synthetic result. Rate changes alone do not establish a cause.",
        )
