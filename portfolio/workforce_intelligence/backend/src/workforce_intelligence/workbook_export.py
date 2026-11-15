"""Exports from existing scoped Gold and assurance contracts."""

from datetime import date
from typing import Literal

from workforce_intelligence.analytics import (
    application_funnel,
    executive_metrics,
    quality_checks,
    reporting_window,
)
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import InvalidOperation, current_dataset
from workforce_intelligence.metric_catalogue import CATALOGUE
from workforce_intelligence.operation_models import Input
from workforce_intelligence.schemas import EntityId
from workforce_intelligence.survey_fixture import ANALYSIS_ID
from workforce_intelligence.surveys import read_survey_report
from workforce_intelligence.workbook_import import ImportPreview
from workforce_intelligence.xlsx import INFO_SHEET, book_bytes, new_book, tab, write_row


class ExportRequest(Input):
    kind: Literal["analytics", "metrics", "quality", "survey"]
    as_of_date: date | None = None
    period_start: date | None = None
    vacancy_id: EntityId | None = None


def export_workbook(database: Database, request: ExportRequest) -> bytes:
    if request.kind != "analytics" and (request.period_start or request.vacancy_id):
        raise InvalidOperation("Period and vacancy filters apply only to analytics exports.")
    if request.kind in ("metrics", "survey") and request.as_of_date:
        raise InvalidOperation("Choose a date only for analytics or data quality exports.")
    book = new_book(f"Workforce {request.kind} export")
    with database.transaction() as conn:
        state = current_dataset(conn)
        info = book[INFO_SHEET]
        write_row(info, ("Scenario", state.scenario_code))
        write_row(info, ("Generation", state.dataset_generation))
        write_row(info, ("Revision", state.revision))
        write_row(info, ("Data refreshed (UTC)", state.refreshed_at))
        window = reporting_window(state, request.as_of_date, request.period_start)
        if request.kind in ("analytics", "quality"):
            write_row(info, ("As of", window.end.isoformat()))
        if request.kind == "analytics":
            write_row(info, ("Period start", window.start.isoformat()))
            write_row(info, ("Application vacancy", request.vacancy_id or "All vacancies"))
            if request.vacancy_id:
                write_row(
                    info,
                    ("Filter scope", "Vacancy selection applies to the application funnel only."),
                )
            report = executive_metrics(conn, state, window)
            funnel = application_funnel(conn, window, request.vacancy_id)
            tab(
                book,
                "Executive metrics",
                ("Metric", "Value", "Unit", "Numerator", "Denominator", "Status"),
                (
                    (
                        item.definition.name,
                        item.current.value,
                        item.definition.unit,
                        item.current.numerator,
                        item.current.denominator,
                        item.current.status,
                    )
                    for item in report.metrics
                ),
            )
            tab(
                book,
                "Application funnel",
                ("Stage", "Applications", "Previous stage conversion"),
                (
                    (
                        stage.stage,
                        stage.application_count,
                        stage.conversion_from_previous.value
                        if stage.conversion_from_previous
                        else None,
                    )
                    for stage in funnel.stages
                ),
            )
        elif request.kind == "metrics":
            tab(
                book,
                "Metric catalogue",
                (
                    "Code",
                    "Metric",
                    "Unit",
                    "Formula",
                    "Numerator",
                    "Denominator",
                    "Grain",
                    "Exclusions",
                    "Caveat",
                    "Version",
                ),
                (
                    (
                        value.code,
                        value.name,
                        value.unit,
                        value.formula,
                        value.numerator,
                        value.denominator,
                        value.grain,
                        value.exclusions,
                        value.caveat,
                        value.version,
                    )
                    for value in CATALOGUE.values()
                ),
            )
        elif request.kind == "quality":
            tab(
                book,
                "Data quality",
                ("Quality check", "Issues"),
                quality_checks(conn, window.end.isoformat()).items(),
            )
        else:
            report = read_survey_report(conn, ANALYSIS_ID)
            if report is None:
                raise InvalidOperation("No reviewed survey report is available.")
            write_row(info, ("Survey", report.title))
            tab(
                book,
                "Published findings",
                (
                    "Finding",
                    "Theme",
                    "Classification",
                    "Severity",
                    "Summary",
                    "Reviewed",
                    "Published",
                ),
                (
                    (
                        finding.id,
                        finding.theme,
                        finding.classification,
                        finding.severity,
                        finding.summary,
                        finding.reviewed_on,
                        finding.published_on,
                    )
                    for finding in report.findings
                ),
            )
            tab(
                book,
                "Permitted evidence",
                ("Finding", "Response", "Synthetic excerpt"),
                (
                    (finding.id, evidence.response_id, evidence.comment)
                    for finding in report.findings
                    for evidence in finding.evidence
                ),
            )
    return book_bytes(book)


def errors_workbook(preview: ImportPreview) -> bytes:
    book = new_book(
        "The row numbers refer to the uploaded template. No raw cell values are exported."
    )
    info = book[INFO_SHEET]
    write_row(info, ("Batch", str(preview.batch_id)))
    write_row(info, ("Source revision", preview.dataset.revision))
    tab(
        book,
        "Validation issues",
        ("Sheet", "Row", "Action", "Result", "Error", "Warning"),
        (
            (row.sheet, row.row, row.action, row.result, row.message, row.warning)
            for row in preview.rows
            if row.message or row.warning
        ),
    )
    return book_bytes(book)
