"""Vacancy lifecycle, cancellation, and actual starts."""

import sqlite3
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Literal

from workforce_intelligence.contracts import add_employment
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    DatasetState,
    DatasetVersion,
    InvalidOperation,
    current_dataset,
)
from workforce_intelligence.operation_store import Change, SourceEditor, duplicate

VacancyStatus = Literal[
    "approved", "advertised", "partially_filled", "filled", "cancelled", "closed"
]
OPEN_STATUSES = ("approved", "advertised", "partially_filled")


@dataclass(frozen=True)
class VacancySnapshot:
    id: str
    title: str
    record_version: int
    status: VacancyStatus
    approved_on: str
    advertised_on: str | None
    closed_on: str | None
    approved_positions: int
    filled_positions: int
    approved_wte: float
    filled_wte: float
    open_wte: float
    over_establishment: bool


def vacancy_snapshots(connection: sqlite3.Connection, as_of: str) -> list[VacancySnapshot]:
    rows = connection.execute(
        """
        WITH fills AS (
            SELECT vacancy_id, COUNT(*) AS positions, SUM(started_fte_milli) AS wte_milli
            FROM silver_starters WHERE started_on <= :as_of GROUP BY vacancy_id
        )
        SELECT vacancy.*, COALESCE(fills.positions, 0) AS filled_positions,
               COALESCE(fills.wte_milli, 0) AS filled_fte_milli
        FROM bronze_vacancies AS vacancy LEFT JOIN fills ON fills.vacancy_id = vacancy.id
        WHERE vacancy.approved_on <= :as_of ORDER BY vacancy.approved_on DESC, vacancy.id
        """,
        {"as_of": as_of},
    )
    return [_vacancy_snapshot(row, as_of) for row in rows]


def _fully_filled(vacancy: sqlite3.Row, filled: int, fte_milli: int) -> bool:
    return filled >= vacancy["approved_positions"] and fte_milli >= vacancy["approved_fte_milli"]


def _vacancy_snapshot(row: sqlite3.Row, as_of: str) -> VacancySnapshot:
    closed = row["closed_on"] if row["closed_on"] and row["closed_on"] <= as_of else None
    advertised = (
        row["advertised_on"] if row["advertised_on"] and row["advertised_on"] <= as_of else None
    )
    if closed:
        status: VacancyStatus = "cancelled" if row["closure_kind"] == "cancelled" else "closed"
    elif _fully_filled(row, row["filled_positions"], row["filled_fte_milli"]):
        status = "filled"
    elif row["filled_positions"]:
        status = "partially_filled"
    else:
        status = "advertised" if advertised else "approved"
    open_milli = (
        max(0, row["approved_fte_milli"] - row["filled_fte_milli"])
        if status in OPEN_STATUSES
        else 0
    )
    return VacancySnapshot(
        id=row["id"],
        title=row["title"],
        record_version=row["record_version"],
        status=status,
        approved_on=row["approved_on"],
        advertised_on=advertised,
        closed_on=closed,
        approved_positions=row["approved_positions"],
        filled_positions=row["filled_positions"],
        approved_wte=row["approved_fte_milli"] / 1000,
        filled_wte=row["filled_fte_milli"] / 1000,
        open_wte=open_milli / 1000,
        over_establishment=bool(row["over_establishment"]),
    )


def _source_fills(connection: sqlite3.Connection, vacancy_id: str) -> sqlite3.Row:
    return connection.execute(
        """
        SELECT COUNT(*) AS positions, COALESCE(SUM(started_fte_milli), 0) AS wte_milli,
               MAX(started_on) AS last_start
        FROM starter_events JOIN offers ON offers.id = starter_events.offer_id
        JOIN candidate_applications AS app ON app.id = offers.application_id
        WHERE app.vacancy_id = ?
        """,
        (vacancy_id,),
    ).fetchone()


def close_vacancy(editor: SourceEditor, vacancy_id: str, day: str, kind: str) -> Change:
    vacancy = editor.versioned("vacancies", vacancy_id, "Vacancy")
    values = {"closed_on": day, "closure_kind": kind}
    if vacancy["closed_on"]:
        return duplicate(vacancy, values)
    if not vacancy["is_approved"]:
        raise InvalidOperation("Approve the vacancy before closing it.")
    fills = _source_fills(editor.connection, vacancy_id)
    if _fully_filled(vacancy, fills["positions"], fills["wte_milli"]):
        raise InvalidOperation("A fully filled vacancy is already complete.")
    latest = editor.connection.execute(
        """
        SELECT MAX(day) FROM (
            SELECT app.received_on AS day FROM candidate_applications app WHERE app.vacancy_id = :vacancy
            UNION ALL
            SELECT event.occurred_on FROM candidate_applications app
            JOIN application_stage_events event ON event.application_id = app.id
            WHERE app.vacancy_id = :vacancy AND event.stage_code != 'probation_completed'
            UNION ALL
            SELECT COALESCE(offer.resolved_on, offer.offered_on) FROM candidate_applications app
            JOIN offers offer ON offer.application_id = app.id WHERE app.vacancy_id = :vacancy
            UNION ALL
            SELECT c.checked_on FROM candidate_applications app
            JOIN offers offer ON offer.application_id = app.id
            JOIN pre_employment_checks c ON c.offer_id = offer.id WHERE app.vacancy_id = :vacancy
            UNION ALL
            SELECT app.disposed_on FROM candidate_applications app WHERE app.vacancy_id = :vacancy
        )
        """,
        {"vacancy": vacancy_id},
    ).fetchone()[0]
    if day < max(
        vacancy["advertised_on"] or vacancy["approved_on"],
        latest or "",
        fills["last_start"] or "",
    ):
        raise InvalidOperation("Closure cannot precede recruitment activity or an actual start.")
    editor.update("vacancies", "id", vacancy_id, values)
    editor.bump("vacancies", vacancy_id)
    return editor.audit(
        "vacancy",
        vacancy_id,
        "cancel_vacancy" if kind == "cancelled" else "close_vacancy",
        {"closed_on": None},
        values,
    )


def cancel_vacancy(
    database: Database,
    *,
    vacancy_id: str,
    record_version: int,
    cancelled_on: date,
    expected: DatasetVersion,
    actor: AuditActor,
) -> tuple[DatasetState, int]:
    with database.transaction(write=True) as connection:
        editor = SourceEditor(
            connection, current_dataset(connection, expected), actor, record_version
        )
        result = close_vacancy(editor, vacancy_id, editor.day(cancelled_on), "cancelled")
        return editor.state, record_version + int(result != "unchanged")


def write_start(
    editor: SourceEditor,
    offer_id: str,
    started_on: date,
    fte_milli: int,
) -> tuple[Change, int, str]:
    if not 1 <= fte_milli <= 1000:
        raise InvalidOperation("Starter FTE must be greater than 0 and at most 1.")
    day = editor.day(started_on)
    offer = editor.require("silver_offers", "id", offer_id, "Offer")
    vacancy_id = offer["vacancy_id"]
    vacancy = editor.versioned("vacancies", vacancy_id, "Vacancy")
    if existing := editor.get("starter_events", "offer_id", offer_id):
        return (
            duplicate(existing, {"started_on": day, "started_fte_milli": fte_milli}),
            vacancy["record_version"],
            existing["employee_id"],
        )
    if vacancy["closed_on"]:
        raise InvalidOperation("The vacancy is already closed.")
    if offer["outcome"] != "accepted" or day < offer["resolved_on"]:
        raise InvalidOperation("A start requires an accepted offer dated on or before the start.")
    application = editor.require(
        "candidate_applications", "id", offer["application_id"], "Application"
    )
    if application["disposition"]:
        raise InvalidOperation("This application has ended.")
    ready = editor.connection.execute(
        """
        SELECT 1 FROM application_stage_events AS confirmed
        JOIN pre_employment_checks AS checks ON checks.offer_id = :offer
          AND checks.checked_on = (SELECT MAX(checked_on) FROM pre_employment_checks
                                   WHERE offer_id = :offer AND checked_on <= :day)
          AND checks.status = 'passed' AND checks.checked_on <= confirmed.occurred_on
        WHERE confirmed.application_id = :application AND confirmed.stage_code = 'start_confirmed'
          AND checks.checked_on >= :accepted AND confirmed.occurred_on <= :day LIMIT 1
        """,
        {
            "offer": offer_id,
            "application": offer["application_id"],
            "accepted": offer["resolved_on"],
            "day": day,
        },
    ).fetchone()
    if ready is None:
        raise InvalidOperation(
            "Complete checks and confirm the start before recording an actual start."
        )
    fills = _source_fills(editor.connection, vacancy_id)
    if not vacancy["over_establishment"] and (
        fills["positions"] >= vacancy["approved_positions"]
        or fills["wte_milli"] + fte_milli > vacancy["approved_fte_milli"]
    ):
        raise InvalidOperation("The starter would exceed the vacancy's approved positions or WTE.")
    editor.budget(vacancy["line_id"], day)
    suffix = offer_id if len(offer_id) <= 56 else sha256(offer_id.encode()).hexdigest()[:32]
    employee_id = f"starter-{suffix}"
    if editor.get("employees", "id", employee_id):
        raise Conflict("The generated starter key is already in use.")
    add_employment(
        editor.connection,
        employee_id=employee_id,
        display_name=f"Demo Starter {suffix[:30]}.",
        line_id=vacancy["line_id"],
        fte_milli=fte_milli,
        start=day,
        created_at=editor.prepare().refreshed_at,
        created_by=editor.actor.uid,
        change_reason="actual_start",
    )
    editor.insert("employee_profiles", {"employee_id": employee_id})
    editor.insert(
        "starter_events",
        {
            "offer_id": offer_id,
            "employee_id": employee_id,
            "started_on": day,
            "started_fte_milli": fte_milli,
        },
    )
    editor.bump("vacancies", vacancy_id)
    editor.bump("candidate_applications", offer["application_id"])
    change = editor.audit(
        "starter",
        offer_id,
        "record_start",
        None,
        {
            "employee_id": employee_id,
            "vacancy_id": vacancy_id,
            "started_on": day,
            "fte_milli": fte_milli,
        },
    )
    return change, vacancy["record_version"] + 1, employee_id


def record_start(
    database: Database,
    *,
    offer_id: str,
    record_version: int,
    started_on: date,
    fte_milli: int,
    expected: DatasetVersion,
    actor: AuditActor,
) -> tuple[DatasetState, int, str]:
    with database.transaction(write=True) as connection:
        editor = SourceEditor(
            connection, current_dataset(connection, expected), actor, record_version
        )
        change, version, employee_id = write_start(editor, offer_id, started_on, fte_milli)
        if change == "unchanged":
            raise Conflict("An actual start already exists for this offer.")
        return editor.state, version, employee_id
