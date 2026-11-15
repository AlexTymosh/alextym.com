"""Vacancy lifecycle, cancellation, and actual starts."""

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Literal

from workforce_intelligence.contracts import add_employment
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    DatasetState,
    DatasetVersion,
    InvalidOperation,
    RecordNotFound,
    advance_revision,
    current_dataset,
    operation_date,
    record_audit,
)

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
    )


def _open_vacancy(connection: sqlite3.Connection, vacancy_id: str, version: int) -> sqlite3.Row:
    vacancy = connection.execute("SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)).fetchone()
    if vacancy is None:
        raise RecordNotFound("Vacancy not found.")
    if vacancy["record_version"] != version:
        raise Conflict("The vacancy changed. Refresh and retry.")
    if vacancy["closed_on"]:
        raise InvalidOperation("The vacancy is already closed.")
    return vacancy


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
        state = current_dataset(connection, expected)
        day = operation_date(state, cancelled_on)
        vacancy = _open_vacancy(connection, vacancy_id, record_version)
        fills = _source_fills(connection, vacancy_id)
        if _fully_filled(vacancy, fills["positions"], fills["wte_milli"]):
            raise InvalidOperation("A fully filled vacancy cannot be cancelled.")
        last_application = connection.execute(
            "SELECT MAX(received_on) FROM candidate_applications WHERE vacancy_id = ?",
            (vacancy_id,),
        ).fetchone()[0]
        if day < max(
            vacancy["advertised_on"] or vacancy["approved_on"],
            last_application or "",
            fills["last_start"] or "",
        ):
            raise InvalidOperation(
                "Cancellation cannot precede advertising, an application, or an actual start."
            )

        connection.execute(
            "UPDATE vacancies SET closed_on = ?, closure_kind = 'cancelled', record_version = ? WHERE id = ?",
            (day, record_version + 1, vacancy_id),
        )
        updated = advance_revision(connection, state)
        record_audit(
            connection,
            updated,
            actor,
            entity_type="vacancy",
            entity_key=vacancy_id,
            action="cancel_vacancy",
            old_values={"closed_on": None},
            new_values={"closed_on": day, "closure_kind": "cancelled"},
        )
        return updated, record_version + 1


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
    if not 1 <= fte_milli <= 1000:
        raise InvalidOperation("Starter FTE must be greater than 0 and at most 1.")
    with database.transaction(write=True) as connection:
        state = current_dataset(connection, expected)
        day = operation_date(state, started_on)
        offer = connection.execute(
            "SELECT * FROM silver_offers WHERE id = ?", (offer_id,)
        ).fetchone()
        if offer is None:
            raise RecordNotFound("Offer not found.")
        vacancy_id = offer["vacancy_id"]
        vacancy = _open_vacancy(connection, vacancy_id, record_version)
        if offer["outcome"] != "accepted" or day < offer["resolved_on"]:
            raise InvalidOperation(
                "A start requires an accepted offer dated on or before the start."
            )
        if connection.execute(
            "SELECT 1 FROM starter_events WHERE offer_id = ?", (offer_id,)
        ).fetchone():
            raise Conflict("An actual start already exists for this offer.")
        ready = connection.execute(
            """
            SELECT 1 FROM application_stage_events AS confirmed
            JOIN application_stage_events AS checks ON checks.application_id = confirmed.application_id
              AND checks.stage_code = 'checks_completed' AND checks.occurred_on <= confirmed.occurred_on
            WHERE confirmed.application_id = ? AND confirmed.stage_code = 'start_confirmed'
              AND checks.occurred_on >= ? AND confirmed.occurred_on <= ? LIMIT 1
            """,
            (offer["application_id"], offer["resolved_on"], day),
        ).fetchone()
        if ready is None:
            raise InvalidOperation(
                "Complete checks and confirm the start before recording an actual start."
            )
        fills = _source_fills(connection, vacancy_id)
        if (
            fills["positions"] >= vacancy["approved_positions"]
            or fills["wte_milli"] + fte_milli > vacancy["approved_fte_milli"]
        ):
            raise InvalidOperation(
                "The starter would exceed the vacancy's approved positions or WTE."
            )
        budget = connection.execute(
            "SELECT 1 FROM establishment_history WHERE line_id = ? AND valid_from <= ? "
            "AND (valid_to IS NULL OR valid_to > ?)",
            (vacancy["line_id"], day, day),
        ).fetchone()
        if budget is None:
            raise InvalidOperation(
                "The vacancy has no active establishment line on the date of start."
            )

        updated = advance_revision(connection, state)
        employee_id = f"starter-{offer_id}"
        add_employment(
            connection,
            employee_id=employee_id,
            display_name=f"Demo Starter {offer_id}.",
            line_id=vacancy["line_id"],
            fte_milli=fte_milli,
            start=day,
            created_at=updated.refreshed_at,
            created_by=actor.uid,
            change_reason="actual_start",
        )
        connection.execute(
            "INSERT INTO starter_events VALUES (?, ?, ?, ?)",
            (offer_id, employee_id, day, fte_milli),
        )
        connection.execute(
            "UPDATE vacancies SET record_version = ? WHERE id = ?", (record_version + 1, vacancy_id)
        )
        record_audit(
            connection,
            updated,
            actor,
            entity_type="starter",
            entity_key=offer_id,
            action="record_start",
            old_values=None,
            new_values={
                "employee_id": employee_id,
                "vacancy_id": vacancy_id,
                "started_on": day,
                "fte_milli": fte_milli,
            },
        )
        return updated, record_version + 1, employee_id
