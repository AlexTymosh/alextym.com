"""Versioned Excel workbook schema. Only approved synthetic inputs are supported."""

from datetime import date
from typing import Annotated, Literal, get_args

from pydantic import Field, TypeAdapter

from workforce_intelligence.dataset import InvalidOperation
from workforce_intelligence.operation_models import Command, Input, Label
from workforce_intelligence.operation_store import Change, SourceEditor, duplicate
from workforce_intelligence.schemas import EntityId

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
WORKBOOK_VERSION = "1"
METADATA_TITLE = "Workforce workbook version"
SYNTHETIC_NOTICE = "Synthetic demonstration data only."
MAX_UPLOAD_BYTES = 1024 * 1024
MAX_ROWS = 500


class SurveyCampaign(Input):
    action: Literal["add_survey_campaign"]
    survey_id: EntityId
    title: Label
    period_start: date
    period_end: date
    invited: Annotated[int, Field(strict=True, ge=1, le=5000)]


COMMENT_CODES = {
    "none": None,
    "rota_pressure": "Synthetic comment: leave more recovery time between busy shifts.",
    "development": "Synthetic comment: protect some time for team training.",
    "communication": "Synthetic comment: share changes earlier when the rota moves.",
    "positive": "Synthetic comment: regular check-ins helped us raise issues early.",
}


class SurveyResponse(Input):
    action: Literal["record_survey_response"]
    id: EntityId
    survey_id: EntityId
    submitted_on: date
    comment_code: Literal["none", "rota_pressure", "development", "communication", "positive"]


WorkbookCommand = Annotated[
    Command | SurveyCampaign | SurveyResponse, Field(discriminator="action")
]
COMMAND_ADAPTER = TypeAdapter(WorkbookCommand)
MODELS = {
    model.model_fields["action"].annotation.__args__[0]: model
    for model in (*get_args(get_args(Command)[0]), SurveyCampaign, SurveyResponse)
}

# Dependency order; same-sheet rows are applied in worksheet order.
SHEETS = {
    "ReferenceData": ("set_reference", "add_establishment_line", "add_campaign"),
    "Employees": ("add_employee", "edit_profile"),
    "Contracts": ("set_contract",),
    "Assignments": ("set_assignment",),
    "Vacancies": ("add_vacancy", "move_vacancy"),
    "Applications": ("add_application", "move_application", "record_interview"),
    "Offers": ("add_offer", "decide_offer"),
    "PreEmploymentChecks": ("record_check",),
    "NewStarters": ("confirm_start", "record_starter", "record_probation"),
    "Learning": ("record_learning",),
    "PDR": ("record_pdr",),
    "Leavers": ("record_leaver",),
    "SurveyResponses": ("add_survey_campaign", "record_survey_response"),
}

KEYS = {
    "set_reference": ("kind", "id"),
    "add_establishment_line": ("id",),
    "add_campaign": ("id",),
    "add_employee": ("employee_id",),
    "edit_profile": ("employee_id",),
    "set_contract": ("employee_id", "effective_from"),
    "set_assignment": ("employee_id", "effective_from"),
    "add_vacancy": ("vacancy_id",),
    "move_vacancy": ("vacancy_id", "transition"),
    "add_application": ("application_id",),
    "move_application": ("application_id", "transition"),
    "record_interview": ("application_id",),
    "add_offer": ("id",),
    "decide_offer": ("offer_id",),
    "record_check": ("offer_id", "checked_on"),
    "confirm_start": ("application_id",),
    "record_starter": ("offer_id",),
    "record_probation": ("employee_id", "occurred_on"),
    "record_learning": ("id",),
    "record_pdr": ("id",),
    "record_leaver": ("employee_id",),
    "add_survey_campaign": ("survey_id",),
    "record_survey_response": ("id",),
}


def columns_for(sheet: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(field for action in SHEETS[sheet] for field in MODELS[action].model_fields)
    )


def add_survey_campaign(editor: SourceEditor, command: SurveyCampaign) -> Change:
    start, end = editor.day(command.period_start), editor.day(command.period_end)
    if end < start:
        raise InvalidOperation("A survey period cannot end before it starts.")
    values = {
        "id": command.survey_id,
        "title": command.title,
        "question": "What helped or made work harder this month?",
        "period_start": start,
        "period_end": end,
        "invited": command.invited,
    }
    if prior := editor.get("survey_campaigns", "id", command.survey_id):
        return duplicate(prior, values)
    editor.insert("survey_campaigns", values)
    return editor.audit("survey_campaign", command.survey_id, command.action, None, values)


def record_survey_response(editor: SourceEditor, command: SurveyResponse) -> Change:
    day = editor.day(command.submitted_on)
    campaign = editor.require("survey_campaigns", "id", command.survey_id, "Survey campaign")
    if editor.get("voice_campaign_settings", "survey_id", command.survey_id):
        raise InvalidOperation("Generate responses through People Voice for this campaign.")
    if not campaign["period_start"] <= day <= campaign["period_end"]:
        raise InvalidOperation("The response falls outside the survey period.")
    values = {
        "id": command.id,
        "survey_id": command.survey_id,
        "submitted_on": day,
        "comment": COMMENT_CODES[command.comment_code],
    }
    if prior := editor.get("survey_responses", "id", command.id):
        return duplicate(prior, values)
    if editor.get("ai_analyses", "survey_id", command.survey_id):
        raise InvalidOperation("Create a new survey for imports. Analysed evidence is fixed.")
    count = editor.connection.execute(
        "SELECT COUNT(*) FROM survey_responses WHERE survey_id = ?", (command.survey_id,)
    ).fetchone()[0]
    if count >= campaign["invited"]:
        raise InvalidOperation("Responses cannot exceed the number invited.")
    editor.insert("survey_responses", values)
    return editor.audit(
        "survey_response",
        command.id,
        command.action,
        None,
        {"survey_id": command.survey_id, "submitted_on": day, "comment_code": command.comment_code},
    )
