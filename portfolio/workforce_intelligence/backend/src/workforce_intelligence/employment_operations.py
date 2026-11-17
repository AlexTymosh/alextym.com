"""Source commands for people, effective employment, and development."""

from datetime import date, timedelta

from workforce_intelligence.contracts import add_employment
from workforce_intelligence.dataset import InvalidOperation
from workforce_intelligence.operation_models import (
    AssignmentSet,
    ContractSet,
    EmployeeCreate,
    EmployeeEdit,
    Learning,
    Leave,
    Pdr,
    Probation,
)
from workforce_intelligence.operation_store import Change, SourceEditor, duplicate, same


def add_employee(editor: SourceEditor, command: EmployeeCreate) -> Change:
    day = editor.day(command.start_on)
    identity = command.employee_id
    fte = int(command.contracted_fte * 1000)
    if row := editor.get("employees", "id", identity):
        duplicate(row, {"display_name": command.display_name})
        contract = editor.covering("employment_contracts", identity, day)
        assignment = editor.covering("organisation_assignments", identity, day)
        if contract and assignment:
            duplicate(
                contract,
                {
                    "valid_from": day,
                    "contracted_fte_milli": fte,
                    "is_substantive": command.substantive,
                },
            )
            return duplicate(assignment, {"valid_from": day, "line_id": command.line_id})
        raise InvalidOperation("Use the existing employee's profile or employment history.")
    editor.budget(command.line_id, day)
    add_employment(
        editor.connection,
        employee_id=identity,
        display_name=command.display_name,
        line_id=command.line_id,
        fte_milli=fte,
        start=day,
        created_by=editor.actor.uid,
        created_at=editor.prepare().refreshed_at,
        change_reason="initial_employment",
        substantive=command.substantive,
    )
    editor.insert("employee_profiles", {"employee_id": identity})
    return editor.audit(
        "employee",
        identity,
        command.action,
        None,
        {
            "display_name": command.display_name,
            "contracted_fte_milli": fte,
            "is_substantive": command.substantive,
            "line_id": command.line_id,
            "valid_from": day,
        },
    )


def edit_profile(editor: SourceEditor, command: EmployeeEdit) -> Change:
    identity = command.employee_id
    employee = editor.versioned("employees", identity, "Employee")
    profile = editor.get("employee_profiles", "employee_id", identity)
    old = {
        key: profile[key] if profile else "not-stated"
        for key in ("age_band", "ethnicity_group", "disability_status")
    }
    new = {key: getattr(command, key) or value for key, value in old.items()}
    if old == new and employee["display_name"] == command.display_name:
        return "unchanged"
    if profile:
        editor.update("employee_profiles", "employee_id", identity, new)
    else:
        editor.insert("employee_profiles", {"employee_id": identity, **new})
    editor.update("employees", "id", identity, {"display_name": command.display_name})
    editor.bump("employees", identity)
    # Demographic edits are synthetic categories; do not disclose them via audit.
    return editor.audit(
        "employee",
        identity,
        command.action,
        {"display_name": employee["display_name"]},
        {
            "display_name": command.display_name,
            "synthetic_demographics_updated": old != new,
        },
    )


def _write_period(
    editor: SourceEditor,
    table: str,
    identity: str,
    day: str,
    end: str | None,
    row,
    attributes: dict,
    action: str,
) -> Change:
    if row and same(row, {"valid_to": end, **attributes}):
        return "unchanged"
    fields = {"valid_from": day, "valid_to": end, **attributes}
    metadata = {
        "created_at": editor.prepare().refreshed_at,
        "created_by": editor.actor.uid,
        "change_reason": action,
    }
    if row and day == row["valid_from"]:
        editor.update(table, "id", row["id"], {**fields, **metadata})
    else:
        if row:
            editor.update(table, "id", row["id"], {"valid_to": day})
        editor.insert(table, {"employee_id": identity, **fields, **metadata})
    editor.bump("employees", identity)
    old = {key: row[key] for key in fields} if row else None
    editor.audit(
        "contract" if table == "employment_contracts" else "assignment",
        identity,
        action,
        old,
        fields,
    )
    return "update" if row and day == row["valid_from"] else "insert"


def set_contract(editor: SourceEditor, command: ContractSet) -> Change:
    identity = command.employee_id
    editor.versioned("employees", identity, "Employee")
    day = editor.day(command.effective_from)
    if editor.covering("organisation_assignments", identity, day) is None:
        raise InvalidOperation("No assignment covers the contract start date.")
    contract = editor.covering("employment_contracts", identity, day)
    profile = editor.get("employee_profiles", "employee_id", identity)
    leave = profile["leaving_date"] if profile else None
    next_start = editor.connection.execute(
        "SELECT MIN(valid_from) FROM employment_contracts WHERE employee_id = ? AND valid_from > ?",
        (identity, day),
    ).fetchone()[0]
    boundary = min((item for item in (leave, next_start) if item), default=None)
    if leave and day >= leave:
        raise InvalidOperation("A contract cannot start on or after the leaving date.")
    end = (
        command.valid_to.isoformat()
        if command.valid_to
        else (contract["valid_to"] if contract else boundary)
    )
    if end and (end <= day or (boundary and end > boundary)):
        raise InvalidOperation(
            "End date must follow the start and not cross the next contract or leaving date."
        )
    starter = editor.get("starter_events", "employee_id", identity)
    if (
        starter
        and day <= starter["started_on"]
        and contract
        and (contract["valid_to"] is None or starter["started_on"] < contract["valid_to"])
        and (not command.substantive or (end and end <= starter["started_on"]))
    ):
        raise InvalidOperation(
            "A recorded starter needs a substantive contract covering the actual start."
        )
    return _write_period(
        editor,
        "employment_contracts",
        identity,
        day,
        end,
        contract,
        {
            "contracted_fte_milli": int(command.contracted_fte * 1000),
            "is_substantive": command.substantive,
        },
        command.action,
    )


def set_assignment(editor: SourceEditor, command: AssignmentSet) -> Change:
    identity = command.employee_id
    editor.versioned("employees", identity, "Employee")
    day = editor.day(command.effective_from)
    editor.active_employee(identity, day)
    row = editor.covering("organisation_assignments", identity, day)
    if row is None:
        raise InvalidOperation("No assignment covers the selected transfer date.")
    if row["line_id"] == command.line_id:
        if (
            command.kind != "transfer"
            and not editor.connection.execute(
                """SELECT 1 FROM promotion_events WHERE employee_id = ? AND occurred_on = ?
                AND to_line_id = ? AND kind = ?""",
                (identity, day, command.line_id, command.kind),
            ).fetchone()
        ):
            raise InvalidOperation("Choose a different establishment line for progression.")
        return "unchanged"
    # Same-day corrections on an explicitly recorded progression would invalidate its destination.
    if editor.connection.execute(
        "SELECT 1 FROM promotion_events WHERE employee_id = ? AND occurred_on = ?",
        (identity, day),
    ).fetchone():
        raise InvalidOperation("This date already has a recorded progression.")
    starter = editor.get("starter_events", "employee_id", identity)
    if (
        starter
        and day <= starter["started_on"]
        and (row["valid_to"] is None or starter["started_on"] < row["valid_to"])
    ):
        raise InvalidOperation("A transfer cannot replace the assignment at an actual start.")
    editor.budget(command.line_id, day)
    result = _write_period(
        editor,
        "organisation_assignments",
        identity,
        day,
        row["valid_to"],
        row,
        {"line_id": command.line_id},
        command.kind,
    )
    if command.kind != "transfer":
        values = {
            "employee_id": identity,
            "occurred_on": day,
            "from_line_id": row["line_id"],
            "to_line_id": command.line_id,
            "kind": command.kind,
        }
        editor.insert("promotion_events", values)
        editor.audit("progression", identity, command.kind, None, values)
    return result


def record_leave(editor: SourceEditor, command: Leave) -> Change:
    identity = command.employee_id
    editor.versioned("employees", identity, "Employee")
    day = editor.day(command.leaving_date)
    values = {"leaving_date": day, "reason": command.reason}
    if existing := editor.get("leaver_events", "employee_id", identity):
        return duplicate(existing, values)
    if command.leaving_date == date.min:
        raise InvalidOperation("Leave must follow the start of employment.")
    editor.active_employee(identity, (command.leaving_date - timedelta(days=1)).isoformat())
    for table in ("organisation_assignments", "employment_contracts"):
        if editor.connection.execute(
            f"SELECT 1 FROM {table} WHERE employee_id = ? AND valid_from >= ?",
            (identity, day),
        ).fetchone():
            raise InvalidOperation("Leave cannot erase a later effective employment record.")
    for table, column in (
        ("learning_events", "occurred_on"),
        ("pdr_events", "occurred_on"),
        ("probation_events", "occurred_on"),
        ("absence_events", "started_on"),
    ):
        if editor.connection.execute(
            f"SELECT 1 FROM {table} WHERE employee_id = ? AND {column} >= ?",
            (identity, day),
        ).fetchone():
            raise InvalidOperation("Leave cannot precede a recorded employee event.")
    for table in ("organisation_assignments", "employment_contracts"):
        editor.connection.execute(
            f"""UPDATE {table} SET valid_to = ? WHERE employee_id = ?
                AND (valid_to IS NULL OR valid_to > ?)""",
            (day, identity, day),
        )
    profile = {
        "employment_status": "Leaver",
        "leaving_date": day,
        "leaving_reason": command.reason,
    }
    if editor.get("employee_profiles", "employee_id", identity):
        editor.update("employee_profiles", "employee_id", identity, profile)
    else:
        editor.insert("employee_profiles", {"employee_id": identity, **profile})
    editor.insert("leaver_events", {"employee_id": identity, **values})
    editor.bump("employees", identity)
    return editor.audit(
        "employee", identity, command.action, {"employment_status": "Active"}, profile
    )


def record_development(editor: SourceEditor, command: Learning | Pdr) -> Change:
    day = editor.day(command.occurred_on)
    identity = command.employee_id
    editor.versioned("employees", identity, "Employee")
    editor.active_employee(identity, day)
    table = "learning_events" if isinstance(command, Learning) else "pdr_events"
    values = {"employee_id": identity, "occurred_on": day}
    values.update(
        {"activity_code": command.activity_code, "completed": command.completed}
        if isinstance(command, Learning)
        else {"status": command.status}
    )
    prior = editor.get(table, "id", command.id)
    if prior:
        duplicate(prior, {"employee_id": identity})
        if same(prior, values):
            return "unchanged"
        editor.update(table, "id", command.id, values)
    else:
        editor.insert(table, {"id": command.id, **values})
    editor.bump("employees", identity)
    return editor.audit(
        "learning" if isinstance(command, Learning) else "pdr",
        command.id,
        command.action,
        {key: prior[key] for key in values} if prior else None,
        values,
    )


def record_probation(editor: SourceEditor, command: Probation) -> Change:
    day = editor.day(command.occurred_on)
    identity = command.employee_id
    editor.versioned("employees", identity, "Employee")
    starter = editor.require("starter_events", "employee_id", identity, "Actual start")
    editor.active_employee(identity, day)
    latest = editor.connection.execute(
        "SELECT * FROM probation_events WHERE employee_id = ? ORDER BY occurred_on DESC LIMIT 1",
        (identity,),
    ).fetchone()
    if latest and same(latest, {"occurred_on": day, "outcome": command.outcome}):
        return "unchanged"
    if day <= starter["started_on"] or (
        latest and (latest["outcome"] != "extended" or day <= latest["occurred_on"])
    ):
        raise InvalidOperation(
            "Probation follows the actual start and a completed outcome is final."
        )
    values = {"employee_id": identity, "occurred_on": day, "outcome": command.outcome}
    editor.insert("probation_events", values)
    if command.outcome != "extended":
        offer = editor.get("offers", "id", starter["offer_id"])
        editor.insert(
            "application_stage_events",
            {
                "application_id": offer["application_id"],
                "stage_code": "probation_completed",
                "occurred_on": day,
            },
        )
        editor.bump("candidate_applications", offer["application_id"])
    editor.bump("employees", identity)
    return editor.audit("probation", identity, command.action, None, values)
