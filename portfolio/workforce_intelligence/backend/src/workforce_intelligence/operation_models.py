"""Typed source commands shared by the member API and workbook importer."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)

from workforce_intelligence.schemas import (
    DatasetRequest,
    EntityId,
    Fte,
    PositiveVersion,
)

Label = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9 .&()/,'+\-]{0,79}$",
    ),
]
DemoName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=48,
        pattern=r"^Demo [A-Za-z0-9][A-Za-z0-9 .\-]{0,40}$",
    ),
]
PositionCount = Annotated[int, Field(strict=True, ge=1, le=100)]
Wte = Annotated[Decimal, Field(gt=0, le=100, decimal_places=3)]
AgeBand = Literal["18-24", "25-34", "35-44", "45-54", "55-64", "65-plus", "not-stated"]
Ethnicity = Literal["white", "mixed", "asian", "black", "other", "not-stated"]
Disability = Literal["yes", "no", "not-stated"]
LeaveReason = Literal["resignation", "retirement", "fixed_term_end", "other"]
ReferenceKind = Literal["organisation", "location", "role", "recruitment_source"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmployeeCreate(Input):
    action: Literal["add_employee"]
    employee_id: EntityId
    display_name: DemoName
    line_id: EntityId
    start_on: date
    contracted_fte: Fte
    substantive: StrictBool = True


class EmployeeEdit(Input):
    action: Literal["edit_profile"]
    employee_id: EntityId
    display_name: DemoName
    age_band: AgeBand | None = None
    ethnicity_group: Ethnicity | None = None
    disability_status: Disability | None = None


class ContractSet(Input):
    action: Literal["set_contract"]
    employee_id: EntityId
    effective_from: date
    valid_to: date | None = None
    contracted_fte: Fte
    substantive: StrictBool = True


class AssignmentSet(Input):
    action: Literal["set_assignment"]
    employee_id: EntityId
    effective_from: date
    line_id: EntityId
    kind: Literal["transfer", "promotion", "internal_appointment"] = "transfer"


class Leave(Input):
    action: Literal["record_leaver"]
    employee_id: EntityId
    leaving_date: date
    reason: LeaveReason


class Learning(Input):
    action: Literal["record_learning"]
    id: EntityId
    employee_id: EntityId
    occurred_on: date
    activity_code: EntityId
    completed: StrictBool = True


class Pdr(Input):
    action: Literal["record_pdr"]
    id: EntityId
    employee_id: EntityId
    occurred_on: date
    status: Literal["due", "completed", "overdue"]


class ReferenceSet(Input):
    action: Literal["set_reference"]
    kind: ReferenceKind
    id: EntityId
    label: Label
    active: StrictBool = True
    pay_band: Literal["2", "3", "4", "5", "6", "7", "8a", "8b", "Not specified"] | None = None

    @model_validator(mode="after")
    def validate_band(self):
        if self.kind != "role" and self.pay_band is not None:
            raise ValueError("Only a role can have a pay band.")
        return self


class EstablishmentLine(Input):
    action: Literal["add_establishment_line"]
    id: EntityId
    organisation_id: EntityId
    location_id: EntityId
    role_id: EntityId
    effective_from: date
    approved_positions: PositionCount
    budgeted_wte: Wte


class Campaign(Input):
    action: Literal["add_campaign"]
    id: EntityId
    label: Label
    opened_on: date


class VacancyCreate(Input):
    action: Literal["add_vacancy"]
    vacancy_id: EntityId
    line_id: EntityId
    title: Label
    requested_on: date
    approved_positions: PositionCount
    approved_wte: Wte
    campaign_id: EntityId | None = None


class VacancyTransition(Input):
    action: Literal["move_vacancy"]
    vacancy_id: EntityId
    occurred_on: date
    transition: Literal["approve", "publish", "close", "cancel"]
    over_establishment_reason: Label | None = None

    @model_validator(mode="after")
    def validate_override(self):
        if self.transition != "approve" and self.over_establishment_reason is not None:
            raise ValueError("Only approval can flag over-establishment.")
        return self


class ApplicationCreate(Input):
    action: Literal["add_application"]
    application_id: EntityId
    vacancy_id: EntityId
    received_on: date
    source_code: EntityId


class ApplicationTransition(Input):
    action: Literal["move_application"]
    application_id: EntityId
    occurred_on: date
    transition: Literal["screened", "shortlisted", "withdrawn", "rejected"]


class Interview(Input):
    action: Literal["record_interview"]
    application_id: EntityId
    occurred_on: date
    outcome: Literal["passed", "unsuccessful"]


class OfferCreate(Input):
    action: Literal["add_offer"]
    id: EntityId
    application_id: EntityId
    offered_on: date


class OfferDecision(Input):
    action: Literal["decide_offer"]
    offer_id: EntityId
    resolved_on: date
    outcome: Literal["accepted", "declined", "withdrawn"]


class Check(Input):
    action: Literal["record_check"]
    offer_id: EntityId
    checked_on: date
    status: Literal["pending", "passed", "failed"]


class ConfirmStart(Input):
    action: Literal["confirm_start"]
    application_id: EntityId
    occurred_on: date
    planned_start_on: date


class Starter(Input):
    action: Literal["record_starter"]
    offer_id: EntityId
    started_on: date
    contracted_fte: Fte


class Probation(Input):
    action: Literal["record_probation"]
    employee_id: EntityId
    occurred_on: date
    outcome: Literal["passed", "extended", "unsuccessful"]


Command = Annotated[
    EmployeeCreate
    | EmployeeEdit
    | ContractSet
    | AssignmentSet
    | Leave
    | Learning
    | Pdr
    | ReferenceSet
    | EstablishmentLine
    | Campaign
    | VacancyCreate
    | VacancyTransition
    | ApplicationCreate
    | ApplicationTransition
    | Interview
    | OfferCreate
    | OfferDecision
    | Check
    | ConfirmStart
    | Starter
    | Probation,
    Field(discriminator="action"),
]


class OperationRequest(DatasetRequest):
    revision: Annotated[int, Field(strict=True, ge=0)]
    record_version: PositiveVersion | None = None
    command: Command
