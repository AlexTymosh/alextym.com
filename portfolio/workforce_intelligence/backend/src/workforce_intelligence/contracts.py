"""Effective-dated Workforce contract commands."""

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
