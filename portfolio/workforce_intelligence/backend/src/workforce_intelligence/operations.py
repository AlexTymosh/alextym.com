"""Run typed source commands against one Workforce dataset revision."""

from workforce_intelligence import employment_operations as employment
from workforce_intelligence import recruitment_operations as recruitment
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    InvalidOperation,
    current_dataset,
)
from workforce_intelligence.operation_models import (
    Command,
    EstablishmentLine,
    OperationRequest,
    ReferenceSet,
    Starter,
)
from workforce_intelligence.operation_store import (
    REFERENCE,
    Change,
    SourceEditor,
    duplicate,
    same,
)
from workforce_intelligence.recruitment import write_start


def set_reference(editor: SourceEditor, command: ReferenceSet) -> Change:
    table = REFERENCE[command.kind]
    row = editor.get(table, "id", command.id)
    values: dict = {"label": command.label, "active": command.active}
    if command.kind == "role" and command.pay_band:
        values["pay_band"] = command.pay_band
        if (
            row
            and row["pay_band"] != command.pay_band
            and editor.connection.execute(
                "SELECT 1 FROM establishment_lines WHERE role_id = ?",
                (command.id,),
            ).fetchone()
        ):
            raise InvalidOperation("Use a new role code for a new pay band on assignment history.")
    if row and same(row, values):
        return "unchanged"
    if editor.connection.execute(
        f"SELECT 1 FROM {table} WHERE label = ? AND id != ?",
        (command.label, command.id),
    ).fetchone():
        raise InvalidOperation("This label already has a reference code.")
    if row:
        editor.update(table, "id", command.id, values)
    else:
        editor.insert(table, {"id": command.id, **values})
    return editor.audit(
        command.kind,
        command.id,
        command.action,
        {key: row[key] for key in values} if row else None,
        values,
    )


def add_line(editor: SourceEditor, command: EstablishmentLine) -> Change:
    day = editor.day(command.effective_from)
    budget = {
        "approved_positions": command.approved_positions,
        "budget_fte_milli": int(command.budgeted_wte * 1000),
        "valid_from": day,
    }
    if budget["budget_fte_milli"] > command.approved_positions * 1000:
        raise InvalidOperation("Establishment WTE cannot exceed the number of positions.")
    keys = {
        "organisation_id": command.organisation_id,
        "location_id": command.location_id,
        "role_id": command.role_id,
    }
    if row := editor.get("establishment_lines", "id", command.id):
        duplicate(row, keys)
        existing = editor.budget(command.id, day)
        return duplicate(existing, budget)
    for kind in ("organisation", "location", "role"):
        editor.reference(REFERENCE[kind], keys[f"{kind}_id"])
    if editor.connection.execute(
        "SELECT 1 FROM establishment_lines WHERE organisation_id = ? AND location_id = ? AND role_id = ?",
        tuple(keys.values()),
    ).fetchone():
        raise InvalidOperation("These reference codes already form an establishment line.")
    editor.insert("establishment_lines", {"id": command.id, **keys})
    editor.insert(
        "establishment_history",
        {
            "line_id": command.id,
            **budget,
            "created_at": editor.prepare().refreshed_at,
            "created_by": editor.actor.uid,
            "change_reason": command.action,
        },
    )
    return editor.audit("establishment", command.id, command.action, None, {**keys, **budget})


def record_starter(editor: SourceEditor, command: Starter) -> Change:
    change, _, _ = write_start(
        editor, command.offer_id, command.started_on, int(command.contracted_fte * 1000)
    )
    return change


HANDLERS = {
    "add_employee": employment.add_employee,
    "edit_profile": employment.edit_profile,
    "set_contract": employment.set_contract,
    "set_assignment": employment.set_assignment,
    "record_leaver": employment.record_leave,
    "record_learning": employment.record_development,
    "record_pdr": employment.record_development,
    "record_probation": employment.record_probation,
    "set_reference": set_reference,
    "add_establishment_line": add_line,
    "add_campaign": recruitment.add_campaign,
    "add_vacancy": recruitment.add_vacancy,
    "move_vacancy": recruitment.move_vacancy,
    "add_application": recruitment.add_application,
    "move_application": recruitment.move_application,
    "record_interview": recruitment.record_interview,
    "add_offer": recruitment.add_offer,
    "decide_offer": recruitment.decide_offer,
    "record_check": recruitment.record_check,
    "confirm_start": recruitment.confirm_start,
    "record_starter": record_starter,
}


def apply_command(editor: SourceEditor, command: Command) -> Change:
    return HANDLERS[command.action](editor, command)


def run_operation(database: Database, request: OperationRequest, actor: AuditActor):
    with database.transaction(write=True) as connection:
        state = current_dataset(connection, request.expected_version())
        if request.revision != state.revision:
            raise Conflict("The source data changed. Refresh and retry.")
        editor = SourceEditor(connection, state, actor, request.record_version)
        change = apply_command(editor, request.command)
        return editor.state, change
