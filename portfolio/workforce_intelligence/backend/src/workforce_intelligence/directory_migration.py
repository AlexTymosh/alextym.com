"""Refresh fixture aliases in place while retaining the underlying employment history."""

import sqlite3
from typing import TYPE_CHECKING

from workforce_intelligence.directory_names import (
    CORE_FEATURED_IDS,
    FEATURED_NAMES,
    FULL_FEATURED_IDS,
    FULL_SEED_VERSION,
    INTERVIEW_SEED_VERSION,
    synthetic_name,
)

if TYPE_CHECKING:
    from workforce_intelligence.dataset import DatasetState

_REFRESH_ACTION = "refresh_employee_directory"


def refresh_employee_directory(connection: sqlite3.Connection) -> None:
    from workforce_intelligence.dataset import (
        AuditActor,
        advance_revision,
        current_dataset,
        record_audit,
    )
    from workforce_intelligence.seed import add_interview_bank_employees

    if not connection.execute("SELECT 1 FROM dataset_state").fetchone():
        return

    state = current_dataset(connection)
    if state.scenario_code == "interview-core":
        featured_ids, seed_version = CORE_FEATURED_IDS, INTERVIEW_SEED_VERSION
    elif state.scenario_code in ("full-controlled", "full-exploratory"):
        featured_ids, seed_version = FULL_FEATURED_IDS, FULL_SEED_VERSION
    else:
        return
    if state.seed_version == seed_version:
        return

    connection.executemany(
        """
        UPDATE employees SET display_name = :name, is_featured_demo_employee = 1,
            display_order = :position, record_version = record_version + 1
        WHERE id = :id
          AND (display_name <> :name OR is_featured_demo_employee <> 1 OR display_order IS NOT :position)
        """,
        [
            {"id": employee_id, "name": name, "position": position}
            for position, (employee_id, name) in enumerate(zip(featured_ids, FEATURED_NAMES), 1)
        ],
    )
    if state.scenario_code == "interview-core":
        add_interview_bank_employees(connection)

    legacy_rows = connection.execute("""
        SELECT e.id
        FROM employees e LEFT JOIN starter_events starter ON starter.employee_id = e.id
        WHERE e.is_featured_demo_employee = 0 AND (
            (e.id GLOB 'demo-[0-9][0-9][0-9][0-9]' AND e.display_name = 'Demo Staff ' || substr(e.id, 6) || '.')
            OR (starter.employee_id IS NOT NULL AND e.id LIKE 'hire-%'
                AND e.display_name = 'Demo Starter ' || substr(e.id, 6) || '.')
            OR (starter.employee_id IS NOT NULL AND e.id LIKE 'starter-%'
                AND e.display_name = 'Demo Starter ' || substr(e.id, 9, 30) || '.')
        )
    """).fetchall()
    connection.executemany(
        """
        UPDATE employees SET display_name = ?, record_version = record_version + 1 WHERE id = ?
        """,
        [(synthetic_name(row["id"]), row["id"]) for row in legacy_rows],
    )

    updated = advance_revision(connection, state)
    connection.execute("UPDATE dataset_state SET seed_version = ?", (seed_version,))
    record_audit(
        connection,
        updated,
        AuditActor("workforce-seed", "req_employee_directory", "seed"),
        entity_type="dataset",
        entity_key=state.dataset_id,
        action=_REFRESH_ACTION,
        old_values={"seed_version": state.seed_version},
        new_values={"seed_version": seed_version},
    )


def has_only_directory_refresh(connection: sqlite3.Connection, state: "DatasetState") -> bool:
    """The first directory refresh on the full fixture leaves recruitment inputs intact."""
    return (
        state.revision == 1
        and connection.execute(
            """
        SELECT 1 FROM audit_events WHERE entity_type = 'dataset' AND entity_key = ?
          AND action = ? AND source_channel = 'seed' AND demo_session_id = ?
        """,
            (state.dataset_id, _REFRESH_ACTION, f"{state.dataset_id}:{state.dataset_generation}"),
        ).fetchone()
        is not None
    )
