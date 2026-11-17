"""Effective-dated Workforce employment commands."""

import sqlite3
from datetime import date

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


def employees_at(
    connection: sqlite3.Connection, day: str, limit: int, offset: int
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT employee.id, employee.display_name, employee.is_featured_demo_employee,
               employee.display_order, employee.record_version,
               contract.contracted_fte_milli / 1000.0 AS contracted_fte,
               unit.label AS organisation, location.label AS location, role.label AS role,
               featured.job_title AS directory_job_title, featured.department AS directory_department,
               COALESCE(featured.title_inferred, 0) AS directory_title_inferred,
               COALESCE(featured.department_inferred, 0) AS directory_department_inferred
        FROM employees AS employee
        LEFT JOIN featured_directory_profiles AS featured ON employee.is_featured_demo_employee = 1
          AND featured.display_order = employee.display_order
        JOIN employment_contracts AS contract ON contract.employee_id = employee.id
          AND contract.valid_from <= :day AND (contract.valid_to IS NULL OR contract.valid_to > :day)
        LEFT JOIN organisation_assignments AS assignment ON assignment.employee_id = employee.id
          AND assignment.valid_from <= :day AND (assignment.valid_to IS NULL OR assignment.valid_to > :day)
        LEFT JOIN establishment_lines AS line ON line.id = assignment.line_id
        LEFT JOIN organisational_units AS unit ON unit.id = line.organisation_id
        LEFT JOIN locations AS location ON location.id = line.location_id
        LEFT JOIN roles AS role ON role.id = line.role_id
        ORDER BY employee.is_featured_demo_employee DESC, employee.display_order, employee.id
        LIMIT :limit OFFSET :offset
        """,
        {"day": day, "limit": limit, "offset": offset},
    ).fetchall()


def add_employment(
    connection: sqlite3.Connection,
    *,
    employee_id: str,
    display_name: str,
    line_id: str,
    fte_milli: int,
    start: str,
    created_at: str,
    created_by: str,
    change_reason: str,
    featured_order: int | None = None,
    substantive: bool = True,
) -> None:
    """Create an employee's initial contract and budget-line assignment."""
    connection.execute(
        "INSERT INTO employees (id, display_name, is_featured_demo_employee, display_order) VALUES (?, ?, ?, ?)",
        (employee_id, display_name, int(featured_order is not None), featured_order),
    )
    connection.execute(
        """
        INSERT INTO employment_contracts (employee_id, contracted_fte_milli, is_substantive,
            valid_from, created_at, created_by, change_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (employee_id, fte_milli, substantive, start, created_at, created_by, change_reason),
    )
    connection.execute(
        """
        INSERT INTO organisation_assignments (employee_id, line_id, valid_from, created_at,
            created_by, change_reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (employee_id, line_id, start, created_at, created_by, change_reason),
    )


def change_fte(
    database: Database,
    *,
    employee_id: str,
    record_version: int,
    effective_from: date,
    fte_milli: int,
    expected: DatasetVersion,
    actor: AuditActor,
) -> tuple[DatasetState, int]:
    if not 1 <= fte_milli <= 1000:
        raise InvalidOperation("Contracted FTE must be greater than 0 and at most 1.")
    with database.transaction(write=True) as connection:
        state = current_dataset(connection, expected)
        effective = operation_date(state, effective_from)
        row = connection.execute(
            """
            SELECT employee.record_version, contract.id, contract.valid_from, contract.valid_to,
                   contract.contracted_fte_milli, contract.is_substantive
            FROM employees AS employee
            LEFT JOIN employment_contracts AS contract ON contract.employee_id = employee.id
                AND contract.valid_from <= ? AND (contract.valid_to IS NULL OR contract.valid_to > ?)
            WHERE employee.id = ?
            """,
            (effective, effective, employee_id),
        ).fetchone()
        if row is None:
            raise RecordNotFound("Employee not found.")
        if row["record_version"] != record_version:
            raise Conflict("The employee changed. Refresh and retry.")
        if row["id"] is None:
            raise InvalidOperation("No employment contract covers the selected effective date.")
        if row["contracted_fte_milli"] == fte_milli:
            return state, record_version

        updated = advance_revision(connection, state)
        if effective == row["valid_from"]:
            connection.execute(
                "UPDATE employment_contracts SET contracted_fte_milli = ? WHERE id = ?",
                (fte_milli, row["id"]),
            )
        else:
            connection.execute(
                "UPDATE employment_contracts SET valid_to = ? WHERE id = ?", (effective, row["id"])
            )
            connection.execute(
                """
                INSERT INTO employment_contracts (employee_id, contracted_fte_milli,
                    is_substantive, valid_from, valid_to, created_at, created_by, change_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'fte_change')
                """,
                (
                    employee_id,
                    fte_milli,
                    row["is_substantive"],
                    effective,
                    row["valid_to"],
                    updated.refreshed_at,
                    actor.uid,
                ),
            )
        connection.execute(
            "UPDATE employees SET record_version = ? WHERE id = ?",
            (record_version + 1, employee_id),
        )
        record_audit(
            connection,
            updated,
            actor,
            entity_type="contract",
            entity_key=employee_id,
            action="change_fte",
            old_values={
                "fte_milli": row["contracted_fte_milli"],
                "valid_from": row["valid_from"],
                "valid_to": row["valid_to"],
            },
            new_values={
                "fte_milli": fte_milli,
                "valid_from": effective,
                "valid_to": row["valid_to"],
            },
        )
        return updated, record_version + 1
