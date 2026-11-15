"""Transaction-scoped helpers for source commands."""

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    DatasetState,
    InvalidOperation,
    RecordNotFound,
    advance_revision,
    operation_date,
    record_audit,
)

REFERENCE = {
    "organisation": "organisational_units",
    "location": "locations",
    "role": "roles",
    "recruitment_source": "recruitment_sources",
}
Change = Literal["insert", "update", "unchanged"]


@dataclass
class SourceEditor:
    connection: sqlite3.Connection
    state: DatasetState
    actor: AuditActor
    record_version: int | None = None
    _changed: bool = field(default=False, init=False)

    def day(self, value: date) -> str:
        return operation_date(self.state, value)

    def get(self, table: str, key: str, value: str) -> sqlite3.Row | None:
        return self.connection.execute(
            f"SELECT * FROM {table} WHERE {key} = ?", (value,)
        ).fetchone()

    def require(self, table: str, key: str, value: str, label: str) -> sqlite3.Row:
        row = self.get(table, key, value)
        if row is None:
            raise RecordNotFound(f"{label} not found.")
        return row

    def versioned(self, table: str, key: str, label: str) -> sqlite3.Row:
        row = self.require(table, "id", key, label)
        if self.record_version is not None and self.record_version != row["record_version"]:
            raise Conflict(f"{label} changed. Refresh and retry.")
        return row

    def bump(self, table: str, key: str) -> None:
        self.connection.execute(
            f"UPDATE {table} SET record_version = record_version + 1 WHERE id = ?",
            (key,),
        )

    # Identifiers here come from fixed service code, never from cell or request text.
    def insert(self, table: str, values: dict) -> None:
        columns = ", ".join(values)
        parameters = ", ".join("?" for _ in values)
        self.connection.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({parameters})",
            tuple(values.values()),
        )

    def update(self, table: str, key: str, identity: str | int, values: dict) -> None:
        columns = ", ".join(f"{column} = ?" for column in values)
        self.connection.execute(
            f"UPDATE {table} SET {columns} WHERE {key} = ?",
            (*values.values(), identity),
        )

    def reference(self, table: str, identity: str) -> None:
        row = self.get(table, "id", identity)
        if row is None or not row["active"]:
            raise InvalidOperation(f"Reference code '{identity}' does not exist or is inactive.")

    def budget(self, line_id: str, day: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT budget.*, line.organisation_id, line.location_id, line.role_id
            FROM establishment_history budget JOIN establishment_lines line ON line.id = budget.line_id
            JOIN organisational_units unit ON unit.id = line.organisation_id AND unit.active = 1
            JOIN locations location ON location.id = line.location_id AND location.active = 1
            JOIN roles role ON role.id = line.role_id AND role.active = 1
            WHERE budget.line_id = ? AND budget.valid_from <= ?
              AND (budget.valid_to IS NULL OR budget.valid_to > ?)
            """,
            (line_id, day, day),
        ).fetchone()
        if row is None:
            raise InvalidOperation(f"Establishment line '{line_id}' is not active on that date.")
        return row

    def covering(self, table: str, employee_id: str, day: str) -> sqlite3.Row | None:
        return self.connection.execute(
            f"""SELECT * FROM {table} WHERE employee_id = ? AND valid_from <= ?
                AND (valid_to IS NULL OR valid_to > ?)""",
            (employee_id, day, day),
        ).fetchone()

    def active_employee(self, employee_id: str, day: str) -> None:
        if not self.covering("employment_contracts", employee_id, day):
            raise InvalidOperation("The employee has no effective contract on that date.")
        profile = self.get("employee_profiles", "employee_id", employee_id)
        if profile and profile["leaving_date"] and day >= profile["leaving_date"]:
            raise InvalidOperation("The date is on or after the employee's leaving date.")

    def prepare(self) -> DatasetState:
        if not self._changed:
            self.state = advance_revision(self.connection, self.state)
            self._changed = True
        return self.state

    def audit(self, entity: str, identity: str, action: str, old: dict | None, new: dict) -> Change:
        record_audit(
            self.connection,
            self.prepare(),
            self.actor,
            entity_type=entity,
            entity_key=identity,
            action=action,
            old_values=old,
            new_values=new,
        )
        return "update" if old is not None else "insert"


def same(row: sqlite3.Row, values: dict) -> bool:
    return all(row[column] == value for column, value in values.items())


def duplicate(row: sqlite3.Row, values: dict) -> Change:
    if same(row, values):
        return "unchanged"
    raise Conflict("That key is already used with different values.")
