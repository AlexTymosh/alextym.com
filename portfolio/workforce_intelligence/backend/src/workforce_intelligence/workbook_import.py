"""Preview in an isolated SQLite snapshot; commit reviewed commands atomically."""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from time import time
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, StrictBool, ValidationError

from workforce_intelligence.analytics import executive_metrics, reporting_window
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    InvalidOperation,
    RecordNotFound,
    current_dataset,
    record_audit,
)
from workforce_intelligence.operation_store import Change, SourceEditor
from workforce_intelligence.operations import apply_command
from workforce_intelligence.schemas import DatasetRequest, DatasetResponse
from workforce_intelligence.workbook_model import (
    COMMAND_ADAPTER,
    KEYS,
    SurveyCampaign,
    SurveyResponse,
    WorkbookCommand,
    add_survey_campaign,
    record_survey_response,
)
from workforce_intelligence.xlsx import BookRow, parse_xlsx

PREVIEW_TTL = 15 * 60
MAX_BATCHES_PER_GENERATION = 128
TIME_WINDOW = 60
_LIMITS = {"preview": (6, 20), "commit": (10, 40), "download": (20, 60)}
_IMPACT_CODES = {"substantive_wte", "vacancy_wte", "open_vacancies", "new_starters"}


class WorkbookThrottled(Exception):
    pass


class RowResult(BaseModel):
    sheet: str
    row: int
    action: str | None = None
    result: Literal["insert", "update", "unchanged", "invalid"]
    message: str | None = None
    warning: str | None = None


class Counts(BaseModel):
    insert: int = 0
    update: int = 0
    unchanged: int = 0
    invalid: int = 0
    warnings: int = 0


class Impact(BaseModel):
    metric: str
    label: str
    before: int | float | None
    after: int | float | None


class ImportPreview(DatasetResponse):
    batch_id: UUID
    counts: Counts
    rows: list[RowResult]
    impact: list[Impact]
    expires_at: int
    committed: bool = False


class ImportConfirmation(DatasetRequest):
    batch_id: UUID
    confirmed: StrictBool


class ImportReceipt(DatasetResponse):
    batch_id: UUID
    counts: Counts
    impact: list[Impact]
    replayed: bool = False


def limit_workbooks(database: Database, actor: AuditActor, operation: str) -> None:
    now = int(time())
    own_limit, shared_limit = _LIMITS[operation]
    with database.transaction(write=True) as conn:
        conn.execute("DELETE FROM workbook_requests WHERE requested_at <= ?", (now - TIME_WINDOW,))
        total, own = conn.execute(
            "SELECT COUNT(*), SUM(actor_uid = ?) FROM workbook_requests WHERE operation = ?",
            (actor.uid, operation),
        ).fetchone()
        if total >= shared_limit or (own or 0) >= own_limit:
            raise WorkbookThrottled
        conn.execute(
            "INSERT INTO workbook_requests (operation, actor_uid, requested_at) VALUES (?, ?, ?)",
            (operation, actor.uid, now),
        )


def _apply(editor: SourceEditor, command: WorkbookCommand) -> Change:
    if isinstance(command, SurveyCampaign):
        return add_survey_campaign(editor, command)
    if isinstance(command, SurveyResponse):
        return record_survey_response(editor, command)
    return apply_command(editor, command)


def _headline(connection, state):
    report = executive_metrics(connection, state, reporting_window(state, None, None))
    return {
        item.definition.code: (item.definition.name, item.current.value)
        for item in report.metrics
        if item.definition.code in _IMPACT_CODES
    }


def _impact(before, after) -> list[Impact]:
    return [
        Impact(metric=code, label=label, before=value, after=after[code][1])
        for code, (label, value) in before.items()
    ]


def _review_rows(connection, state, rows: list[BookRow], actor: AuditActor):
    counts = Counts()
    results: list[RowResult] = []
    commands: list[dict] = []
    seen: set[tuple] = set()
    for row in rows:
        command = row.command
        prefix = {
            "sheet": row.sheet,
            "row": row.number,
            "action": command.action if command else None,
        }
        error = row.error
        if command is not None:
            key = (command.action, *(getattr(command, name) for name in KEYS[command.action]))
            if key in seen:
                error = "This business key appears twice in this workbook."
            else:
                seen.add(key)
        if command is None or error:
            counts.invalid += 1
            results.append(RowResult(**prefix, result="invalid", message=error))
            continue
        connection.execute("SAVEPOINT workbook_row")
        editor = SourceEditor(connection, state, actor)
        try:
            change = _apply(editor, command)
        except (Conflict, InvalidOperation, RecordNotFound, sqlite3.IntegrityError) as failure:
            connection.execute("ROLLBACK TO workbook_row")
            counts.invalid += 1
            results.append(
                RowResult(
                    **prefix,
                    result="invalid",
                    message="The row violates a source constraint."
                    if isinstance(failure, sqlite3.IntegrityError)
                    else str(failure),
                )
            )
        else:
            setattr(counts, change, getattr(counts, change) + 1)
            warning = (
                "Matched existing values; this row makes no change."
                if change == "unchanged"
                else "Approves an explicit exception to establishment capacity."
                if getattr(command, "over_establishment_reason", None)
                else None
            )
            counts.warnings += int(warning is not None)
            results.append(RowResult(**prefix, result=change, warning=warning))
            commands.append(command.model_dump(mode="json", exclude_unset=True))
        finally:
            connection.execute("RELEASE workbook_row")
    return counts, results, commands


def preview_import(database: Database, actor: AuditActor, content: bytes) -> ImportPreview:
    rows = parse_xlsx(content)
    fingerprint = sha256(content).hexdigest()
    now = int(time())
    actor = replace(actor, channel="excel")
    with closing(sqlite3.connect(":memory:")) as snapshot:
        snapshot.row_factory = sqlite3.Row
        snapshot.execute("PRAGMA foreign_keys = ON")
        with database.transaction() as conn:
            state = current_dataset(conn)
            if prior := _prior_preview(conn, actor, state, fingerprint, now):
                return prior
            conn.backup(snapshot)
        before = _headline(snapshot, state)
        counts, results, commands = _review_rows(snapshot, state, rows, actor)
        impact = _impact(before, _headline(snapshot, state)) if counts.invalid == 0 else []
    preview = ImportPreview(
        dataset=state,
        batch_id=uuid4(),
        rows=results,
        counts=counts,
        impact=impact,
        expires_at=now + PREVIEW_TTL,
    )
    with database.transaction(write=True) as conn:
        current = current_dataset(conn, state)
        if current.revision != state.revision:
            raise Conflict(
                "Source records changed while this workbook was checked. Preview it again."
            )
        if prior := _prior_preview(conn, actor, state, fingerprint, now):
            return prior
        conn.execute(
            "DELETE FROM import_batches WHERE receipt_json IS NULL AND created_at <= ?",
            (now - PREVIEW_TTL,),
        )
        if (
            conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]
            >= MAX_BATCHES_PER_GENERATION
        ):
            raise InvalidOperation(
                "This dataset reached its import batch limit. Reset or load a new dataset."
            )
        conn.execute(
            """
            INSERT INTO import_batches (id, actor_uid, dataset_generation, source_revision,
                                        file_hash, created_at, preview_json, commands_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(preview.batch_id),
                actor.uid,
                state.dataset_generation,
                state.revision,
                fingerprint,
                now,
                preview.model_dump_json(),
                json.dumps([] if counts.invalid else commands),
            ),
        )
    return preview


def _prior_preview(conn, actor, state, file_hash: str, now: int) -> ImportPreview | None:
    prior = conn.execute(
        """
        SELECT preview_json, receipt_json FROM import_batches WHERE actor_uid = ? AND dataset_generation = ?
          AND source_revision = ? AND file_hash = ? AND (created_at > ? OR receipt_json IS NOT NULL)
        """,
        (actor.uid, state.dataset_generation, state.revision, file_hash, now - PREVIEW_TTL),
    ).fetchone()
    if prior:
        return ImportPreview.model_validate_json(prior["preview_json"]).model_copy(
            update={"committed": prior["receipt_json"] is not None}
        )
    return None


def _owned_batch(conn, actor: AuditActor, identity: UUID):
    row = conn.execute(
        "SELECT * FROM import_batches WHERE id = ? AND actor_uid = ?", (str(identity), actor.uid)
    ).fetchone()
    if row is None:
        raise RecordNotFound("Import batch not found.")
    return row


def read_preview(database: Database, actor: AuditActor, identity: UUID) -> ImportPreview:
    with database.transaction() as conn:
        row = _owned_batch(conn, actor, identity)
        if not row["receipt_json"] and row["created_at"] + PREVIEW_TTL <= int(time()):
            raise Conflict("This preview expired. Upload the workbook again.")
        return ImportPreview.model_validate_json(row["preview_json"])


def commit_import(
    database: Database, actor: AuditActor, command: ImportConfirmation
) -> ImportReceipt:
    if not command.confirmed:
        raise InvalidOperation("Confirm the preview before importing.")
    actor = replace(actor, channel="excel")
    failure = None
    with database.transaction(write=True) as conn:
        state = current_dataset(conn, command.expected_version())
        row = _owned_batch(conn, actor, command.batch_id)
        if row["dataset_generation"] != state.dataset_generation:
            raise Conflict("The demo dataset changed. Preview a new batch.")
        if row["receipt_json"]:
            return ImportReceipt.model_validate_json(row["receipt_json"]).model_copy(
                update={"replayed": True}
            )
        if row["source_revision"] != state.revision or row["created_at"] + PREVIEW_TTL <= int(
            time()
        ):
            raise Conflict(
                "The preview expired or the source data changed. Validate the workbook again."
            )
        preview = ImportPreview.model_validate_json(row["preview_json"])
        if preview.counts.invalid:
            raise InvalidOperation("Correct all rejected rows before confirming the import.")
        editor = SourceEditor(conn, state, actor)
        before = _headline(conn, state)
        conn.execute("SAVEPOINT workbook_commit")
        try:
            for fields, checked in zip(json.loads(row["commands_json"]), preview.rows, strict=True):
                if _apply(editor, COMMAND_ADAPTER.validate_python(fields)) != checked.result:
                    raise Conflict("A row no longer matches its preview.")
            receipt = ImportReceipt(
                dataset=editor.state,
                batch_id=command.batch_id,
                counts=preview.counts,
                impact=_impact(before, _headline(conn, editor.state)),
            )
            if receipt.impact != preview.impact:
                raise Conflict("The dashboard changes no longer match the preview.")
            audit_state = replace(editor.state, refreshed_at=datetime.now(UTC).isoformat())
            record_audit(
                conn,
                audit_state,
                actor,
                entity_type="import_batch",
                entity_key=str(command.batch_id),
                action="confirm_import",
                old_values=None,
                new_values=preview.counts.model_dump(),
            )
        except (
            Conflict,
            InvalidOperation,
            RecordNotFound,
            sqlite3.IntegrityError,
            ValidationError,
        ) as exc:
            conn.execute("ROLLBACK TO workbook_commit")
            conn.execute(
                "UPDATE import_batches SET last_failure_at = ? WHERE id = ?",
                (int(time()), str(command.batch_id)),
            )
            failure = exc
        else:
            conn.execute(
                "UPDATE import_batches SET receipt_json = ?, last_failure_at = NULL WHERE id = ?",
                (receipt.model_dump_json(), str(command.batch_id)),
            )
        finally:
            conn.execute("RELEASE workbook_commit")
    if failure is not None:
        raise Conflict(
            "The import was rolled back. Retry the preview or validate a fresh workbook."
        ) from failure
    return receipt
