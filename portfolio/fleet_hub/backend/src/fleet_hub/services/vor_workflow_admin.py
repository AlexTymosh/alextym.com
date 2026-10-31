"""V2 workflow template library; ticket stage snapshots are immutable when referenced.

No external service access, no v1 access, no automatic vehicle status updates.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fleet_hub.services import vor_data


def _steps(value: str) -> list[str]:
    try:
        steps = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Template steps are invalid JSON") from exc
    if not isinstance(steps, list) or not all(isinstance(s, str) and s.strip() for s in steps):
        raise ValueError("Template stages must be non-empty strings")
    return steps


def _label(label: str) -> str:
    label = label.strip()
    if not (3 <= len(label) <= 100):
        raise ValueError("Stage/name must be 3–100 characters")
    return label


def _get(db: Any, code: str) -> Any:
    row = db.execute(
        "SELECT code,name,steps_json FROM workflow_templates WHERE code=?", (code,)
    ).fetchone()
    if row is None:
        raise ValueError("Workflow not found")
    return row


def _usage(db: Any, code: str) -> int:
    return int(db.execute("SELECT COUNT(*) FROM tickets WHERE scenario=?", (code,)).fetchone()[0])


def catalogue() -> dict:
    with vor_data.database() as db:
        records = db.execute(
            "SELECT code,name,steps_json FROM workflow_templates ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return {
            "workflows": [
                {
                    "code": r["code"],
                    "name": r["name"],
                    "steps": _steps(r["steps_json"]),
                    "tickets_using": _usage(db, r["code"]),
                    "custom": r["code"].startswith("custom_"),
                }
                for r in records
            ]
        }


def create(name: str, first_stage: str) -> dict:
    name, first_stage = _label(name), _label(first_stage)
    with vor_data.database() as db:
        if db.execute(
            "SELECT 1 FROM workflow_templates WHERE lower(name)=lower(?)", (name,)
        ).fetchone():
            raise ValueError("A workflow with that name already exists")
        code = "custom_" + uuid.uuid4().hex[:14]
        db.execute(
            "INSERT INTO workflow_templates(code,name,steps_json) VALUES(?,?,?)",
            (code, name, json.dumps([first_stage], ensure_ascii=False)),
        )
        db.commit()
        return {"code": code, "name": name, "steps": [first_stage]}


def rename(code: str, name: str) -> dict:
    name = _label(name)
    with vor_data.database() as db:
        _get(db, code)
        if db.execute(
            "SELECT 1 FROM workflow_templates WHERE lower(name)=lower(?) AND code<>?", (name, code)
        ).fetchone():
            raise ValueError("A workflow with that name already exists")
        db.execute("UPDATE workflow_templates SET name=? WHERE code=?", (name, code))
        db.commit()
        return {"ok": True}


def add_stage(code: str, label: str) -> dict:
    label = _label(label)
    with vor_data.database() as db:
        record = _get(db, code)
        steps = _steps(record["steps_json"])
        if len(steps) >= 32:
            raise ValueError("Maximum 32 stages per workflow")
        steps.append(label)
        db.execute(
            "UPDATE workflow_templates SET steps_json=? WHERE code=?", (json.dumps(steps), code)
        )
        db.commit()
        return {"index": len(steps) - 1}


def _used_stage(db: Any, code: str, index: int) -> int:
    return int(
        db.execute(
            """SELECT COUNT(*) FROM ticket_steps s
      JOIN tickets t ON t.id=s.ticket_id WHERE t.scenario=? AND s.step_index=?""",
            (code, index),
        ).fetchone()[0]
    )


def change_stage(code: str, index: int, label: str) -> dict:
    label = _label(label)
    with vor_data.database() as db:
        record = _get(db, code)
        steps = _steps(record["steps_json"])
        if not (0 <= index < len(steps)):
            raise ValueError("Stage does not exist")
        if _used_stage(db, code, index):
            raise ValueError(
                "Stage is already used in existing tickets; its history cannot be changed"
            )
        steps[index] = label
        db.execute(
            "UPDATE workflow_templates SET steps_json=? WHERE code=?", (json.dumps(steps), code)
        )
        db.commit()
        return {"ok": True}


def remove_stage(code: str, index: int) -> dict:
    with vor_data.database() as db:
        record = _get(db, code)
        steps = _steps(record["steps_json"])
        if not (0 <= index < len(steps)):
            raise ValueError("Stage does not exist")
        if len(steps) == 1:
            raise ValueError("A workflow must contain at least one stage")
        # Deleting a stage renumbers those after it. Protect any existing ticket
        # that has a snapshot at this OR any later index, including closed cases.
        count = db.execute(
            """SELECT COUNT(*) FROM ticket_steps s JOIN tickets t ON t.id=s.ticket_id
          WHERE t.scenario=? AND s.step_index>=?""",
            (code, index),
        ).fetchone()[0]
        if count:
            raise ValueError(
                f"Cannot delete: {count} recorded ticket stage(s) depend on this position"
            )
        steps.pop(index)
        db.execute(
            "UPDATE workflow_templates SET steps_json=? WHERE code=?", (json.dumps(steps), code)
        )
        db.commit()
        return {"ok": True}


def remove_workflow(code: str) -> dict:
    with vor_data.database() as db:
        _get(db, code)
        number = _usage(db, code)
        if number:
            raise ValueError(
                f"Cannot delete workflow: referenced by {number} existing ticket(s), including history"
            )
        # Vehicles can retain a selected scenario even if no ticket does.
        assigned = db.execute("SELECT COUNT(*) FROM vehicles WHERE scenario=?", (code,)).fetchone()[
            0
        ]
        if assigned:
            raise ValueError(f"Cannot delete workflow: currently assigned to {assigned} vehicle(s)")
        db.execute("DELETE FROM workflow_templates WHERE code=?", (code,))
        db.commit()
        return {"ok": True}
