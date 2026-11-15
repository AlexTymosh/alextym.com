"""HTTP request and response contracts for the Workforce data core."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from workforce_intelligence.analytics import (
    ApplicationFunnel,
    ExecutiveMetrics,
    MetricComparison,
    ReportingWindow,
)
from workforce_intelligence.dataset import DatasetState, DatasetVersion
from workforce_intelligence.metric_catalogue import MetricDefinition
from workforce_intelligence.recruitment_sources import RecruitmentSourceReport
from workforce_intelligence.recruitment import VacancySnapshot, VacancyStatus
from workforce_intelligence.surveys import SurveyReport
from workforce_intelligence.workforce_trend import WorkforceTrend

EntityId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]
Fte = Annotated[Decimal, Field(gt=0, le=1, decimal_places=3)]


class ErrorDetail(BaseModel):
    detail: str


class DatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: UUID
    dataset_generation: PositiveVersion

    def expected_version(self) -> DatasetVersion:
        return DatasetVersion(str(self.dataset_id), self.dataset_generation)


class RecordRequest(DatasetRequest):
    record_version: PositiveVersion


class FteChange(RecordRequest):
    effective_from: date
    contracted_fte: Fte


class VacancyCancellation(RecordRequest):
    cancelled_on: date


class ActualStart(RecordRequest):
    offer_id: EntityId
    started_on: date
    contracted_fte: Fte


class ResetRequest(DatasetRequest):
    confirmed: StrictBool
    idempotency_key: UUID

    @model_validator(mode="after")
    def require_confirmation(self):
        if not self.confirmed:
            raise ValueError("Reset requires confirmation.")
        return self


class SeedRequest(ResetRequest):
    mode: Literal["controlled", "exploratory"]
    generation_seed: Annotated[int, Field(strict=True, ge=0, le=2**32 - 1)] | None = None

    @model_validator(mode="after")
    def check_seed_mode(self):
        if self.mode == "controlled" and self.generation_seed is not None:
            raise ValueError("Controlled mode always uses the published seed.")
        return self


class DatasetResponse(BaseModel):
    dataset: DatasetState
    synthetic: Literal[True] = True


class MutationResponse(DatasetResponse):
    record_version: int


class StarterResponse(MutationResponse):
    employee_id: str


class ResetResponse(DatasetResponse):
    reset_generation: int
    replayed: bool


class EmployeeSummary(BaseModel):
    id: str
    display_name: str
    is_featured_demo_employee: bool
    display_order: int | None
    record_version: int
    contracted_fte: float
    organisation: str | None
    location: str | None
    role: str | None


class EmployeePage(DatasetResponse):
    as_of_date: str
    items: list[EmployeeSummary]
    next_offset: int | None


class VacancyLifecycle(DatasetResponse):
    as_of_date: str
    status_counts: dict[VacancyStatus, int]
    items: list[VacancySnapshot]
    next_offset: int | None


class QualityResponse(DatasetResponse):
    as_of_date: str
    quality_status: Literal["passed", "review_required"]
    issues: dict[str, int]


class ExecutiveResponse(QualityResponse):
    executive: ExecutiveMetrics


class WorkforceTrendResponse(QualityResponse):
    trend: WorkforceTrend


class RecruitmentSourceResponse(DatasetResponse):
    report: RecruitmentSourceReport


class FunnelResponse(QualityResponse):
    funnel: ApplicationFunnel


class CatalogueResponse(BaseModel):
    metrics: list[MetricDefinition]


class SurveyReportResponse(DatasetResponse):
    report: SurveyReport


class InsightQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["explain_vacancy_rate"]
    as_of_date: date | None = None
    period_start: date | None = None


class InsightResponse(QualityResponse):
    intent: Literal["explain_vacancy_rate"]
    window: ReportingWindow
    metric: MetricComparison
    report_section: Literal["executive"] = "executive"
    limitation: str
