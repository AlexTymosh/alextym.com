"""Project-owned HTTP router. Host applies shared Firebase grant dependency.

This package must not import website security implementations or other projects.
Every project route is mounted with `require_workforce_member` by the host.
"""

import sqlite3
from collections import Counter
from dataclasses import replace
from datetime import date
from secrets import randbits
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from workforce_intelligence.analytics import (
    application_funnel,
    executive_metrics,
    quality_checks,
    reporting_window,
)
from workforce_intelligence.architecture import ArchitectureResponse, layer_examples
from workforce_intelligence.contracts import change_fte, employees_at
from workforce_intelligence.database import DatabaseUnavailable
from workforce_intelligence.dataset import DatasetState, current_dataset, reset_dataset
from workforce_intelligence.forecasting import (
    ForecastHistory,
    ForecastMetric,
    ForecastRequest,
    forecast_history,
)
from workforce_intelligence.http import Db, Member, WorkforceRoute, audit_actor
from workforce_intelligence.inclusive_recruitment import (
    inclusive_recruitment,
    suppress_inclusive_report,
)
from workforce_intelligence.metric_catalogue import CATALOGUE
from workforce_intelligence.operation_models import OperationRequest
from workforce_intelligence.operation_reads import (
    Section,
    audit_values,
    employee_details,
    establishment_options,
    read_section,
)
from workforce_intelligence.operations import run_operation
from workforce_intelligence.planning_runs import (
    ForecastRun,
    ScenarioRun,
    read_scenario,
    run_forecast,
    run_scenario,
)
from workforce_intelligence.recruitment import (
    cancel_vacancy,
    record_start,
    vacancy_snapshots,
)
from workforce_intelligence.recruitment_sources import recruitment_sources
from workforce_intelligence.scale_seed import FULL_SEED
from workforce_intelligence.scenarios import ScenarioInputs, ScenarioRequest
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
    InclusiveRecruitmentResponse,
    InsightQuery,
    InsightResponse,
    MutationResponse,
    QualityResponse,
    RecruitmentSourceResponse,
    ResetRequest,
    ResetResponse,
    SeedRequest,
    StarterResponse,
    SurveyReportResponse,
    VacancyAgeingResponse,
    VacancyCancellation,
    VacancyLifecycle,
    WorkforceTrendResponse,
)
from workforce_intelligence.seed import INTERVIEW_SEED
from workforce_intelligence.survey_fixture import ANALYSIS_ID
from workforce_intelligence.surveys import read_survey_report
from workforce_intelligence.vacancy_ageing import vacancy_ageing
from workforce_intelligence.voice_analysis import (
    AnalyseRequest,
    RunResponse,
    VoiceProvider,
    get_voice_provider,
    run_analysis,
)
from workforce_intelligence.voice_analytics import VoiceAnalyticsResponse, analyse_survey
from workforce_intelligence.voice_campaigns import (
    CampaignCreate,
    CampaignResponse,
    GenerateResponses,
    VoiceWorkspace,
    create_campaign,
    generate_responses,
    workspace,
)
from workforce_intelligence.voice_review import (
    ActionCreate,
    ActionUpdate,
    ReviewRequest,
    ReviewWorkspace,
    create_action,
    read_review,
    review_signal,
    update_action,
)
from workforce_intelligence.workbook_export import ExportRequest, errors_workbook, export_workbook
from workforce_intelligence.workbook_http import (
    FILE_RESPONSE,
    UPLOAD_REQUEST,
    download,
    read_upload,
    throttle,
)
from workforce_intelligence.workbook_import import (
    ImportConfirmation,
    ImportPreview,
    ImportReceipt,
    commit_import,
    preview_import,
    read_preview,
)
from workforce_intelligence.workforce_trend import workforce_trend
from workforce_intelligence.xlsx import template

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
Provider = Annotated[VoiceProvider | None, Depends(get_voice_provider)]


class OperationResult(DatasetResponse):
    change: Literal["insert", "update", "unchanged"]


class OperationPage(DatasetResponse):
    items: list[dict]
    next_offset: int | None


class EmployeeDetails(DatasetResponse):
    employee: dict


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


@router.get("/employees/{employee_id}")
def employee(employee_id: PathId, database: Db, as_of_date: date | None = None) -> EmployeeDetails:
    with database.transaction() as connection:
        state = current_dataset(connection)
        day = reporting_window(state, as_of_date, None).end.isoformat()
        return EmployeeDetails(
            dataset=state, employee=employee_details(connection, employee_id, day)
        )


@router.get("/operations/establishment")
def establishment(database: Db, limit: Limit = 25, offset: Offset = 0) -> OperationPage:
    with database.transaction() as connection:
        state = current_dataset(connection)
        items, next_offset = establishment_options(connection, state.as_of_date, limit, offset)
        return OperationPage(dataset=state, items=items, next_offset=next_offset)


@router.get("/operations/{section}")
def operation_section(
    section: Section, database: Db, limit: Limit = 25, offset: Offset = 0
) -> OperationPage:
    with database.transaction() as connection:
        state = current_dataset(connection)
        items, next_offset = read_section(connection, section, limit, offset)
        return OperationPage(
            dataset=state,
            items=audit_values(items) if section == "audit" else items,
            next_offset=next_offset,
        )


@router.post("/operations")
def operation(command: OperationRequest, database: Db, actor: Member) -> OperationResult:
    state, change = run_operation(database, command, actor)
    return OperationResult(dataset=state, change=change)


@router.get("/import/template", response_class=Response, responses=FILE_RESPONSE)
def workbook_template(database: Db, actor: Member) -> Response:
    throttle(database, actor, "download")
    return download(template(), "template")


@router.post("/import/validate", openapi_extra=UPLOAD_REQUEST)
async def validate_workbook(request: Request, database: Db, actor: Member) -> ImportPreview:
    await run_in_threadpool(throttle, database, actor, "preview")
    content = await read_upload(request)
    return await run_in_threadpool(preview_import, database, actor, content)


@router.post("/import/commit")
def confirm_workbook(command: ImportConfirmation, database: Db, actor: Member) -> ImportReceipt:
    throttle(database, actor, "commit")
    return commit_import(database, actor, command)


@router.get("/import/{batch_id}/errors", response_class=Response, responses=FILE_RESPONSE)
def workbook_issues(batch_id: UUID, database: Db, actor: Member) -> Response:
    throttle(database, actor, "download")
    return download(errors_workbook(read_preview(database, actor, batch_id)), "import-issues")


@router.post("/export", response_class=Response, responses=FILE_RESPONSE)
def export(command: ExportRequest, database: Db, actor: Member) -> Response:
    throttle(database, actor, "download")
    return download(export_workbook(database, command), command.kind)


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


@router.get("/analytics/vacancy-ageing")
def vacancy_ageing_report(database: Db, as_of_date: date | None = None) -> VacancyAgeingResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        cutoff = reporting_window(state, as_of_date, None).end
        quality = _quality(connection, state, cutoff.isoformat())
        return VacancyAgeingResponse(
            **quality.model_dump(), ageing=vacancy_ageing(connection, cutoff)
        )


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
            **quality.model_dump(),
            executive=executive_metrics(connection, state, window),
        )


@router.get("/analytics/workforce-trend")
def monthly_workforce_trend(
    database: Db, as_of_date: date | None = None, period_start: date | None = None
) -> WorkforceTrendResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        # Without an explicit date filter, chart the complete observed history.
        # Other executive KPIs retain their existing current-month default.
        start = period_start or date.fromisoformat(state.history_start)
        window = reporting_window(state, as_of_date, start)
        quality = _quality(connection, state, window.end.isoformat())
        return WorkforceTrendResponse(
            **quality.model_dump(), trend=workforce_trend(connection, window)
        )


@router.get("/analytics/inclusive-recruitment")
def inclusive_recruitment_report(request: Request, database: Db) -> InclusiveRecruitmentResponse:
    # No dates, organisation, role or other filters: avoid small-cell reconstruction.
    if request.query_params:
        raise HTTPException(
            status_code=422, detail="Demographic aggregates do not permit query filters."
        )
    with database.transaction() as connection:
        state = current_dataset(connection)
        report = inclusive_recruitment(connection, as_of_date=state.as_of_date)
        # A released baseline must be immutable and reproducible. Any edit or
        # exploratory seed can reveal a small group by subtracting two reads.
        baseline = (
            state.revision == 0
            and state.scenario_code == FULL_SEED.scenario_code
            and state.generation_seed == FULL_SEED.generation_seed
            and state.seed_version == FULL_SEED.seed_version
        )
        if not baseline:
            report = suppress_inclusive_report(
                report,
                "Suppressed: demographic detail is available only for the "
                "unmodified, reproducible controlled dataset.",
            )
        return InclusiveRecruitmentResponse(dataset=state, report=report)


@router.get("/analytics/recruitment-sources")
def recruitment_source_breakdown(
    database: Db,
    as_of_date: date | None = None,
    period_start: date | None = None,
    campaign_id: EntityId | None = None,
    organisation_id: EntityId | None = None,
    location_id: EntityId | None = None,
    role_id: EntityId | None = None,
) -> RecruitmentSourceResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, as_of_date, period_start)
        return RecruitmentSourceResponse(
            dataset=state,
            report=recruitment_sources(
                connection,
                window,
                campaign_id=campaign_id,
                organisation_id=organisation_id,
                location_id=location_id,
                role_id=role_id,
            ),
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
            **quality.model_dump(),
            funnel=application_funnel(connection, window, vacancy_id),
        )


@router.get("/metrics")
def metric_catalogue() -> CatalogueResponse:
    return CatalogueResponse(metrics=list(CATALOGUE.values()))


@router.get("/forecast/history")
def actual_months(
    metric: ForecastMetric, database: Db, as_of_date: date | None = None
) -> ForecastHistory:
    with database.transaction() as connection:
        return forecast_history(connection, current_dataset(connection), as_of_date, metric)


@router.post("/forecast")
def create_forecast(command: ForecastRequest, database: Db, actor: Member) -> ForecastRun:
    return run_forecast(database, command, actor)


@router.post("/scenarios")
def create_scenario(command: ScenarioRequest, database: Db, actor: Member) -> ScenarioRun:
    return run_scenario(database, command, actor)


@router.get("/scenarios")
def scenario_baseline() -> ScenarioInputs:
    return ScenarioInputs()


@router.get("/scenarios/{run_id}")
def scenario(run_id: UUID, database: Db) -> ScenarioRun:
    return read_scenario(database, run_id)


@router.get("/data-quality")
def data_quality(database: Db, as_of_date: date | None = None) -> QualityResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        cutoff = reporting_window(state, as_of_date, None).end.isoformat()
        return _quality(connection, state, cutoff)


@router.get("/architecture/layers")
def architecture_layers(database: Db, as_of_date: date | None = None) -> ArchitectureResponse:
    with database.transaction() as connection:
        state = current_dataset(connection)
        cutoff = reporting_window(state, as_of_date, None).end
        quality = _quality(connection, state, cutoff.isoformat())
        return ArchitectureResponse(**quality.model_dump(), layers=layer_examples(connection, cutoff))


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
        dataset=result.dataset,
        reset_generation=result.reset_generation,
        replayed=result.replayed,
    )


@router.post("/demo/seed")
def seed(command: SeedRequest, database: Db, actor: Member) -> ResetResponse:
    baseline = FULL_SEED
    if command.mode == "exploratory":
        baseline = replace(
            FULL_SEED,
            scenario_code="full-exploratory",
            generation_seed=command.generation_seed
            if command.generation_seed is not None
            else randbits(32),
        )
    result = reset_dataset(
        database,
        baseline,
        expected=command.expected_version(),
        actor=actor,
        idempotency_key=str(command.idempotency_key),
        request_kind=f"seed:{command.mode}:{command.generation_seed}",
    )
    return ResetResponse(
        dataset=result.dataset, reset_generation=result.reset_generation, replayed=result.replayed
    )


@router.get("/surveys")
def people_voice_workspace(database: Db) -> VoiceWorkspace:
    return workspace(database)


@router.post("/surveys", status_code=201)
def add_survey(command: CampaignCreate, database: Db, actor: Member) -> CampaignResponse:
    return create_campaign(database, actor, command)


@router.post("/surveys/{survey_id}/generate")
def generate_survey(
    survey_id: PathId, command: GenerateResponses, database: Db, actor: Member
) -> CampaignResponse:
    return generate_responses(database, actor, survey_id, command)


@router.get("/surveys/{survey_id}/analytics")
def survey_analytics(
    survey_id: PathId,
    database: Db,
    dimension: str = "service",
    weight_by: str = "service",
    theme: str = "development",
    trim_min: float = 0.5,
    trim_max: float = 2,
) -> VoiceAnalyticsResponse:
    return analyse_survey(database, survey_id, dimension, weight_by, theme, trim_min, trim_max)


@router.post("/surveys/{survey_id}/analyse")
def analyse_campaign(
    survey_id: PathId, command: AnalyseRequest, database: Db, actor: Member, provider: Provider
) -> RunResponse:
    return run_analysis(database, actor, survey_id, command, provider)


@router.get("/surveys/{survey_id}/review")
def survey_reviews(
    survey_id: PathId, database: Db, analysis_id: EntityId | None = None
) -> ReviewWorkspace:
    return read_review(database, survey_id, analysis_id)


@router.post("/surveys/signals/{signal_id}/review")
def decide_signal(
    signal_id: PathId, command: ReviewRequest, database: Db, actor: Member
) -> ReviewWorkspace:
    return review_signal(database, actor, signal_id, command)


@router.post("/surveys/signals/{signal_id}/actions", status_code=201)
def add_management_action(
    signal_id: PathId, command: ActionCreate, database: Db, actor: Member
) -> ReviewWorkspace:
    return create_action(database, actor, signal_id, command)


@router.patch("/surveys/actions/{action_id}")
def update_management_action(
    action_id: PathId, command: ActionUpdate, database: Db, actor: Member
) -> ReviewWorkspace:
    return update_action(database, actor, action_id, command)


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
