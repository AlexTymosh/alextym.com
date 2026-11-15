"""Simulated vacancy and application workflows with chronological event rules."""

from datetime import timedelta

from workforce_intelligence.dataset import InvalidOperation
from workforce_intelligence.operation_models import (
    ApplicationCreate,
    ApplicationTransition,
    Campaign,
    Check,
    ConfirmStart,
    Interview,
    OfferCreate,
    OfferDecision,
    VacancyCreate,
    VacancyTransition,
)
from workforce_intelligence.operation_store import Change, SourceEditor, duplicate
from workforce_intelligence.recruitment import close_vacancy


def add_campaign(editor: SourceEditor, command: Campaign) -> Change:
    values = {
        "id": command.id,
        "label": command.label,
        "opened_on": editor.day(command.opened_on),
    }
    if row := editor.get("recruitment_campaigns", "id", command.id):
        return duplicate(row, values)
    editor.insert("recruitment_campaigns", values)
    return editor.audit("campaign", command.id, command.action, None, values)


def add_vacancy(editor: SourceEditor, command: VacancyCreate) -> Change:
    day = editor.day(command.requested_on)
    wte = int(command.approved_wte * 1000)
    if wte > command.approved_positions * 1000:
        raise InvalidOperation("Requested WTE cannot exceed the number of positions.")
    values = {
        "id": command.vacancy_id,
        "line_id": command.line_id,
        "title": command.title,
        "requested_on": day,
        "approved_positions": command.approved_positions,
        "approved_fte_milli": wte,
        "campaign_id": command.campaign_id,
    }
    if row := editor.get("vacancies", "id", command.vacancy_id):
        return duplicate(row, values)
    editor.budget(command.line_id, day)
    if command.campaign_id:
        campaign = editor.require("recruitment_campaigns", "id", command.campaign_id, "Campaign")
        if campaign["opened_on"] > day:
            raise InvalidOperation("A vacancy cannot be requested before its campaign opens.")
    editor.insert("vacancies", {**values, "is_approved": False, "approved_on": day})
    return editor.audit("vacancy", command.vacancy_id, command.action, None, values)


def _over_capacity(editor: SourceEditor, vacancy, budget, day: str) -> bool:
    conn = editor.connection
    occupied, occupied_wte = conn.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(contracted_fte_milli), 0)
        FROM silver_substantive_employment
        WHERE line_id = ? AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)
        """,
        (vacancy["line_id"], day, day),
    ).fetchone()
    open_positions, open_wte = conn.execute(
        """
        WITH fills AS (
            SELECT vacancy_id, COUNT(*) AS positions, SUM(started_fte_milli) AS wte
            FROM silver_starters WHERE started_on <= :day GROUP BY vacancy_id
        )
        SELECT COALESCE(SUM(MAX(v.approved_positions - COALESCE(f.positions, 0), 0)), 0),
               COALESCE(SUM(MAX(v.approved_fte_milli - COALESCE(f.wte, 0), 0)), 0)
        FROM bronze_vacancies v LEFT JOIN fills f ON f.vacancy_id = v.id
        WHERE v.line_id = :line AND v.approved_on <= :day
          AND (v.closed_on IS NULL OR v.closed_on > :day)
        """,
        {"day": day, "line": vacancy["line_id"]},
    ).fetchone()
    return (
        occupied + open_positions + vacancy["approved_positions"] > budget["approved_positions"]
        or occupied_wte + open_wte + vacancy["approved_fte_milli"] > budget["budget_fte_milli"]
    )


def move_vacancy(editor: SourceEditor, command: VacancyTransition) -> Change:
    day = editor.day(command.occurred_on)
    identity = command.vacancy_id
    if command.transition in ("cancel", "close"):
        return close_vacancy(
            editor,
            identity,
            day,
            "cancelled" if command.transition == "cancel" else "administrative",
        )
    row = editor.versioned("vacancies", identity, "Vacancy")
    if command.transition == "approve":
        values = {
            "approved_on": day,
            "is_approved": True,
            "over_establishment": command.over_establishment_reason is not None,
            "over_establishment_reason": command.over_establishment_reason,
        }
        if row["is_approved"]:
            return duplicate(row, values)
        if day < row["requested_on"]:
            raise InvalidOperation("Approval cannot precede the vacancy request.")
        budget = editor.budget(row["line_id"], day)
        if _over_capacity(editor, row, budget, day) and not command.over_establishment_reason:
            raise InvalidOperation(
                "This exceeds establishment capacity. Supply an explicit exception reason."
            )
    else:
        values = {"advertised_on": day}
        if row["advertised_on"]:
            return duplicate(row, values)
        if not row["is_approved"] or row["closed_on"] or day < row["approved_on"]:
            raise InvalidOperation("Publish an approved, open vacancy on or after approval.")
        editor.budget(row["line_id"], day)
    editor.update("vacancies", "id", identity, values)
    editor.bump("vacancies", identity)
    return editor.audit(
        "vacancy",
        identity,
        command.transition,
        {key: row[key] for key in values},
        values,
    )


def _accepts_activity(editor: SourceEditor, vacancy_id: str, day: str) -> None:
    row = editor.require("vacancies", "id", vacancy_id, "Vacancy")
    # Date-only closure is effective after the recorded closing day. This also permits
    # historical Excel backfills after the Vacancies sheet has applied a closure.
    if (
        not row["advertised_on"]
        or day < row["advertised_on"]
        or (row["closed_on"] and day > row["closed_on"])
    ):
        raise InvalidOperation("Recruitment activity requires a published, open vacancy.")


def add_application(editor: SourceEditor, command: ApplicationCreate) -> Change:
    day = editor.day(command.received_on)
    identity = command.application_id
    values = {
        "id": identity,
        "vacancy_id": command.vacancy_id,
        "received_on": day,
        "source_code": command.source_code,
    }
    if row := editor.get("candidate_applications", "id", identity):
        return duplicate(row, values)
    _accepts_activity(editor, command.vacancy_id, day)
    editor.reference("recruitment_sources", command.source_code)
    editor.insert("candidate_applications", values)
    return editor.audit("application", identity, command.action, None, values)


def _stage_day(editor: SourceEditor, application_id: str, stage: str) -> str | None:
    return editor.connection.execute(
        "SELECT MIN(occurred_on) FROM application_stage_events WHERE application_id = ? AND stage_code = ?",
        (application_id, stage),
    ).fetchone()[0]


def _stage(editor: SourceEditor, identity: str, stage: str, day: str) -> dict:
    fields = {"application_id": identity, "stage_code": stage, "occurred_on": day}
    editor.insert("application_stage_events", fields)
    return fields


def _active_application(editor: SourceEditor, row, day: str) -> None:
    _accepts_activity(editor, row["vacancy_id"], day)
    if row["disposition"] or day < row["received_on"]:
        raise InvalidOperation("The application has ended or the event precedes receipt.")


def move_application(editor: SourceEditor, command: ApplicationTransition) -> Change:
    identity = command.application_id
    row = editor.versioned("candidate_applications", identity, "Application")
    day = editor.day(command.occurred_on)
    transition = command.transition
    if transition in ("screened", "shortlisted"):
        if existing := _stage_day(editor, identity, transition):
            if existing == day:
                return "unchanged"
            raise InvalidOperation("This stage has already been recorded.")
        _active_application(editor, row, day)
        screened = _stage_day(editor, identity, "screened")
        if transition == "shortlisted" and (not screened or day < screened):
            raise InvalidOperation("Shortlisting must follow screening.")
        fields = _stage(editor, identity, transition, day)
    else:
        fields = {"disposition": transition, "disposed_on": day}
        if row["disposition"]:
            return duplicate(row, fields)
        _active_application(editor, row, day)
        offer = editor.get("offers", "application_id", identity)
        if offer and (offer["outcome"] != "accepted" or transition != "withdrawn"):
            raise InvalidOperation("Resolve a pending offer through the offer workflow.")
        if offer and editor.get("starter_events", "offer_id", offer["id"]):
            raise InvalidOperation("An application cannot end after the employee has started.")
        last_stage = editor.connection.execute(
            "SELECT MAX(occurred_on) FROM application_stage_events WHERE application_id = ?",
            (identity,),
        ).fetchone()[0]
        last_check = (
            editor.connection.execute(
                "SELECT MAX(checked_on) FROM pre_employment_checks WHERE offer_id = ?",
                (offer["id"],),
            ).fetchone()[0]
            if offer
            else None
        )
        if day < max(
            row["received_on"],
            last_stage or "",
            last_check or "",
            offer["resolved_on"] if offer else "",
        ):
            raise InvalidOperation("The end date cannot precede recorded recruitment activity.")
        editor.update("candidate_applications", "id", identity, fields)
    editor.bump("candidate_applications", identity)
    return editor.audit(
        "application",
        identity,
        transition,
        {"disposition": None} if transition in ("withdrawn", "rejected") else None,
        fields,
    )


def record_interview(editor: SourceEditor, command: Interview) -> Change:
    identity = command.application_id
    row = editor.versioned("candidate_applications", identity, "Application")
    day = editor.day(command.occurred_on)
    values = {
        "application_id": identity,
        "interviewed_on": day,
        "outcome": command.outcome,
    }
    if prior := editor.get("interviews", "application_id", identity):
        return duplicate(prior, values)
    _active_application(editor, row, day)
    shortlisted = _stage_day(editor, identity, "shortlisted")
    if not shortlisted or day < shortlisted:
        raise InvalidOperation("Interview must follow shortlisting.")
    if legacy := _stage_day(editor, identity, "interviewed"):
        if legacy != day:
            raise InvalidOperation("Use the existing interview's date to record its outcome.")
    else:
        _stage(editor, identity, "interviewed", day)
    editor.insert("interviews", values)
    if command.outcome == "unsuccessful":
        editor.update(
            "candidate_applications",
            "id",
            identity,
            {"disposition": "rejected", "disposed_on": day},
        )
    editor.bump("candidate_applications", identity)
    return editor.audit("interview", identity, command.action, None, values)


def add_offer(editor: SourceEditor, command: OfferCreate) -> Change:
    day = editor.day(command.offered_on)
    identity = command.application_id
    row = editor.versioned("candidate_applications", identity, "Application")
    values = {"id": command.id, "application_id": identity, "offered_on": day}
    if prior := editor.get("offers", "id", command.id):
        return duplicate(prior, values)
    if editor.get("offers", "application_id", identity):
        raise InvalidOperation("This application already has an offer.")
    _active_application(editor, row, day)
    interview = editor.get("interviews", "application_id", identity)
    if not interview or interview["outcome"] != "passed" or day < interview["interviewed_on"]:
        raise InvalidOperation("A conditional offer requires a successful interview.")
    editor.insert("offers", values)
    editor.bump("candidate_applications", identity)
    return editor.audit("offer", command.id, command.action, None, values)


def decide_offer(editor: SourceEditor, command: OfferDecision) -> Change:
    offer = editor.require("offers", "id", command.offer_id, "Offer")
    app = editor.versioned("candidate_applications", offer["application_id"], "Application")
    day = editor.day(command.resolved_on)
    values = {"resolved_on": day, "outcome": command.outcome}
    if offer["outcome"]:
        return duplicate(offer, values)
    _active_application(editor, app, day)
    if day < offer["offered_on"]:
        raise InvalidOperation("An offer decision cannot precede the offer.")
    editor.update("offers", "id", command.offer_id, values)
    editor.bump("candidate_applications", app["id"])
    return editor.audit("offer", command.offer_id, command.action, {"outcome": None}, values)


def _latest_check(editor: SourceEditor, offer_id: str):
    return editor.connection.execute(
        "SELECT * FROM pre_employment_checks WHERE offer_id = ? ORDER BY checked_on DESC LIMIT 1",
        (offer_id,),
    ).fetchone()


def record_check(editor: SourceEditor, command: Check) -> Change:
    day = editor.day(command.checked_on)
    offer = editor.require("offers", "id", command.offer_id, "Offer")
    app = editor.versioned("candidate_applications", offer["application_id"], "Application")
    values = {"offer_id": command.offer_id, "checked_on": day, "status": command.status}
    prior = editor.connection.execute(
        "SELECT * FROM pre_employment_checks WHERE offer_id = ? AND checked_on = ?",
        (command.offer_id, day),
    ).fetchone()
    if prior:
        return duplicate(prior, values)
    _active_application(editor, app, day)
    if offer["outcome"] != "accepted" or day < offer["resolved_on"]:
        raise InvalidOperation("Checks require an accepted offer.")
    latest = _latest_check(editor, command.offer_id)
    if latest and (latest["status"] == "passed" or day <= latest["checked_on"]):
        raise InvalidOperation("Record checks chronologically. Passed checks are complete.")
    editor.insert("pre_employment_checks", values)
    if command.status == "passed":
        _stage(editor, app["id"], "checks_completed", day)
    editor.bump("candidate_applications", app["id"])
    return editor.audit("check", command.offer_id, command.action, None, values)


def confirm_start(editor: SourceEditor, command: ConfirmStart) -> Change:
    day = editor.day(command.occurred_on)
    identity = command.application_id
    app = editor.versioned("candidate_applications", identity, "Application")
    planned = command.planned_start_on.isoformat()
    if existing := _stage_day(editor, identity, "start_confirmed"):
        if (existing, app["planned_start_on"]) == (day, planned):
            return "unchanged"
        raise InvalidOperation("A start is already confirmed for this application.")
    _active_application(editor, app, day)
    if not timedelta(0) <= command.planned_start_on - command.occurred_on <= timedelta(days=365):
        raise InvalidOperation("Choose a planned start within one year after confirmation.")
    offer = editor.get("offers", "application_id", identity)
    latest = (
        _latest_check(editor, offer["id"]) if offer and offer["outcome"] == "accepted" else None
    )
    if not latest or latest["status"] != "passed" or latest["checked_on"] > day:
        raise InvalidOperation("Confirm the start after pre-employment checks pass.")
    _stage(editor, identity, "start_confirmed", day)
    editor.update("candidate_applications", "id", identity, {"planned_start_on": planned})
    editor.bump("candidate_applications", identity)
    return editor.audit(
        "application",
        identity,
        command.action,
        {"planned_start_on": None},
        {"confirmed_on": day, "planned_start_on": planned},
    )
