"""Explicit review, safe publication and the action tracker."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, model_validator

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    InvalidOperation,
    RecordNotFound,
    current_dataset,
)
from workforce_intelligence.operation_store import SourceEditor
from workforce_intelligence.schemas import DatasetRequest, DatasetResponse, EntityId
from workforce_intelligence.voice_analysis import (
    MAX_AI_COMMENTS,
    Classification,
    Compact,
    Severity,
    Theme,
    _run_card,
    redact,
)
from workforce_intelligence.voice_analytics import priority, protected, ratio
from workforce_intelligence.voice_campaigns import campaign
from workforce_intelligence.voice_taxonomy import THEMES

ACTION_TEAMS = (
    "Workforce planning",
    "People team",
    "Learning and development",
    "Clinical assurance",
    "Operations",
    "Recruitment",
)
Team = Literal[*ACTION_TEAMS]


class ReviewRequest(DatasetRequest):
    action: Literal["confirm", "amend", "reject", "publish", "split", "merge"]
    rationale: Compact
    theme: Theme | None = None
    subtheme: Compact | None = None
    classification: Classification | None = None
    severity: Severity | None = None
    keep_response_ids: (
        Annotated[list[EntityId], Field(min_length=1, max_length=MAX_AI_COMMENTS)] | None
    ) = None
    merge_signal_id: EntityId | None = None

    @model_validator(mode="after")
    def validate_edit(self):
        edited = (
            self.theme,
            self.subtheme,
            self.classification,
            self.severity,
            self.keep_response_ids,
        )
        if any(value is not None for value in edited) and self.action not in (
            "amend",
            "split",
            "merge",
        ):
            raise ValueError("Only an amendment, split or merge can change a finding.")
        if self.action == "split" and not self.keep_response_ids:
            raise ValueError("Select the evidence for the new finding.")
        if (self.action == "merge") != (self.merge_signal_id is not None):
            raise ValueError("Choose a second finding only when merging.")
        return self


class ActionCreate(DatasetRequest):
    title: Compact
    team: Team
    due_on: date
    baseline: Compact
    target: Compact
    expected_benefit: Compact


class ActionUpdate(DatasetRequest):
    status: Literal["in_progress", "closed"]
    notes: Compact
    closure_evidence: Compact | None = None

    @model_validator(mode="after")
    def validate_closure(self):
        if (self.status == "closed") != (self.closure_evidence is not None):
            raise ValueError("Closing an action requires closure evidence.")
        return self


class ReviewWorkspace(DatasetResponse):
    runs: list[dict]
    selected_run: dict | None
    signals: list[dict]
    actions: list[dict]
    teams: list[str]


def _signals(connection, run, minimum: int) -> list[dict]:
    output = []
    sample = len(json.loads(run["response_ids"]))
    for row in connection.execute(
        """
        SELECT signal.*, detail.theme_code, detail.subtheme, detail.state, detail.original_json, detail.priority_json
        FROM ai_signals signal JOIN voice_signal_details detail ON detail.signal_id = signal.id
        WHERE signal.analysis_id = ?
        """,
        (run["id"],),
    ):
        excerpts = [
            dict(item)
            for item in connection.execute(
                "SELECT response_id, excerpt FROM voice_evidence_spans WHERE signal_id = ? ORDER BY response_id",
                (row["id"],),
            )
        ]
        safe = not protected(sample, len(excerpts), minimum)
        score = json.loads(row["priority_json"])
        original = json.loads(row["original_json"])
        history = [
            dict(item)
            for item in connection.execute(
                "SELECT action, rationale, actor, occurred_at FROM voice_review_events WHERE signal_id = ? ORDER BY id",
                (row["id"],),
            )
        ]
        output.append(
            {
                "id": row["id"],
                "state": row["state"],
                "theme_code": row["theme_code"] if safe else None,
                "theme": row["theme"] if safe else "Suppressed signal",
                "subtheme": row["subtheme"] if safe else None,
                "classification": row["classification"] if safe else None,
                "severity": row["severity"] if safe else None,
                "summary": row["summary"] if safe else None,
                "evidence": excerpts if safe else [],
                "unique_responses": len(excerpts) if safe else None,
                "prevalence": ratio(len(excerpts), sample) if safe else None,
                "priority": score if safe else None,
                "urgent": score["priority_human_review"],
                "review_history": history,
                "published_on": row["published_on"],
                "original_classification": original["classification"] if safe else None,
                "publication_eligible": safe,
            }
        )
    return sorted(
        output,
        key=lambda item: (
            not item["urgent"],
            -(item["priority"] or {}).get("score", 0),
            item["id"],
        ),
    )


def read_review(
    database: Database, survey_id: str, analysis_id: str | None = None
) -> ReviewWorkspace:
    with database.transaction() as connection:
        state = current_dataset(connection)
        info = campaign(connection, survey_id)
        rows = connection.execute(
            "SELECT * FROM voice_analysis_runs WHERE survey_id = ? ORDER BY started_at DESC LIMIT 20",
            (survey_id,),
        ).fetchall()
        selected = (
            next((row for row in rows if row["id"] == analysis_id), None)
            if analysis_id
            else rows[0]
            if rows
            else None
        )
        if analysis_id and selected is None:
            raise RecordNotFound("Analysis not found in this campaign.")
        signals = _signals(connection, selected, info["anonymity_min"]) if selected else []
        selected_card = _run_card(selected) if selected else None
        if (
            selected_card
            and selected["result_json"]
            and all(item["publication_eligible"] for item in signals)
        ):
            selected_card["summary"] = json.loads(selected["result_json"])["summary"]
        actions = []
        if selected:
            actions = [
                dict(row)
                for row in connection.execute(
                    """
                SELECT action.*, tracking.created_on, tracking.baseline, tracking.target,
                       tracking.expected_benefit, tracking.notes, tracking.closure_evidence
                FROM management_actions action JOIN voice_action_tracking tracking ON tracking.id = action.id
                JOIN gold_voice_published_findings gold ON gold.id = action.signal_id AND gold.analysis_id = ?
                ORDER BY action.due_on, action.id LIMIT 60
                """,
                    (selected["id"],),
                )
            ]
        return ReviewWorkspace(
            dataset=state,
            selected_run=selected_card,
            runs=[_run_card(row) for row in rows],
            signals=signals,
            actions=actions,
            teams=list(ACTION_TEAMS),
        )


def _current_signal(editor, identity):
    source = editor.require("ai_signals", "id", identity, "Finding")
    details = editor.require("voice_signal_details", "signal_id", identity, "Review")
    run = editor.require("voice_analysis_runs", "id", source["analysis_id"], "Analysis")
    return source, details, run


def _evidence(connection, signal_id):
    return {
        row["response_id"]: row["excerpt"]
        for row in connection.execute(
            "SELECT response_id, excerpt FROM voice_evidence_spans WHERE signal_id = ?",
            (signal_id,),
        )
    }


def _set_evidence(editor, signal_id, evidence):
    editor.connection.execute("DELETE FROM voice_evidence_spans WHERE signal_id = ?", (signal_id,))
    editor.connection.execute(
        "DELETE FROM survey_signal_evidence WHERE signal_id = ?", (signal_id,)
    )
    for identity, excerpt in evidence.items():
        editor.insert("survey_signal_evidence", {"signal_id": signal_id, "response_id": identity})
        editor.insert(
            "voice_evidence_spans",
            {"signal_id": signal_id, "response_id": identity, "excerpt": excerpt},
        )


def _review_event(editor, signal_id, action, decision, rationale, changes):
    day = editor.prepare().refreshed_at
    if decision:
        values = {
            "decision": decision,
            "review_kind": "Explicit analyst review",
            "review_rationale": rationale,
            "reviewed_on": day,
        }
        if editor.get("analyst_reviews", "signal_id", signal_id):
            editor.update("analyst_reviews", "signal_id", signal_id, values)
        else:
            editor.insert(
                "analyst_reviews", {"id": f"review-{uuid4().hex}", "signal_id": signal_id, **values}
            )
    editor.insert(
        "voice_review_events",
        {
            "signal_id": signal_id,
            "action": action,
            "rationale": rationale,
            "actor": editor.actor.uid,
            "occurred_at": day,
            "changes_json": json.dumps(changes),
        },
    )
    editor.audit("survey_signal", signal_id, action, None, changes)


def _amend(editor, identity, source, details, command, evidence, sample, minimum):
    theme = command.theme or details["theme_code"]
    level = command.severity or source["severity"]
    subtheme = redact(command.subtheme) if command.subtheme else details["subtheme"]
    label = command.classification or source["classification"]
    if not evidence:
        raise InvalidOperation("A finding must retain at least one validated excerpt.")
    prevalence = None if protected(sample, len(evidence), minimum) else ratio(len(evidence), sample)
    score = priority(
        theme,
        level,
        prevalence,
        serious=label == "Safety concern"
        or json.loads(details["priority_json"])["priority_human_review"],
    )
    _set_evidence(editor, identity, evidence)
    # The original summary remains in immutable output; the visible wording reflects the revised label.
    editor.update(
        "ai_signals",
        "id",
        identity,
        {
            "theme": THEMES[theme],
            "classification": label,
            "severity": level,
            "summary": f"Analyst-reviewed excerpts relate to {THEMES[theme].lower()}. See the evidence and review rationale.",
        },
    )
    editor.update(
        "voice_signal_details",
        "signal_id",
        identity,
        {
            "theme_code": theme,
            "subtheme": subtheme,
            "state": "amended",
            "priority_json": json.dumps(score),
        },
    )
    return {
        "theme": theme,
        "classification": label,
        "severity": level,
        "evidence_count": len(evidence),
    }


def review_signal(
    database: Database, actor: AuditActor, identity: str, command: ReviewRequest
) -> ReviewWorkspace:
    with database.transaction(write=True) as connection:
        editor = SourceEditor(
            connection, current_dataset(connection, command.expected_version()), actor
        )
        source, details, run = _current_signal(editor, identity)
        survey_id, run_id = run["survey_id"], run["id"]
        info = campaign(connection, survey_id)
        evidence = _evidence(connection, identity)
        sample = len(json.loads(run["response_ids"]))
        threshold = info["anonymity_min"]
        rationale = redact(command.rationale)
        if details["state"] in ("published", "rejected"):
            raise Conflict("This finding has already been published or rejected.")
        if command.action == "publish":
            if details["state"] not in ("confirmed", "amended"):
                raise InvalidOperation("Confirm or amend the finding before publishing.")
            if protected(sample, len(evidence), threshold):
                raise InvalidOperation("This finding does not meet the publication anonymity rule.")
            editor.update(
                "ai_signals", "id", identity, {"published_on": editor.prepare().refreshed_at}
            )
            editor.update("voice_signal_details", "signal_id", identity, {"state": "published"})
            _review_event(editor, identity, "publish", None, rationale, {"state": "published"})
        elif command.action in ("confirm", "reject"):
            next_state = "confirmed" if command.action == "confirm" else "rejected"
            editor.update("voice_signal_details", "signal_id", identity, {"state": next_state})
            _review_event(
                editor, identity, command.action, next_state, rationale, {"state": next_state}
            )
        else:
            selected = set(command.keep_response_ids or evidence)
            if not selected <= set(evidence):
                raise InvalidOperation("An edit can use only this finding's validated evidence.")
            kept = {key: value for key, value in evidence.items() if key in selected}
            if command.action == "merge":
                other_source, other, _ = _current_signal(editor, command.merge_signal_id)
                if (
                    other_source["analysis_id"] != run_id
                    or other_source["id"] == identity
                    or other["state"] in ("published", "rejected")
                ):
                    raise InvalidOperation("Merge two unpublished findings from the same analysis.")
                kept = {**_evidence(connection, other_source["id"]), **kept}
                editor.update(
                    "voice_signal_details", "signal_id", other_source["id"], {"state": "rejected"}
                )
                _review_event(
                    editor,
                    other_source["id"],
                    "merge_source",
                    "rejected",
                    rationale,
                    {"merged_into": identity},
                )
            if command.action == "split":
                if len(kept) == len(evidence):
                    raise InvalidOperation("A split must leave evidence on both findings.")
                split_id = f"vs-{uuid4().hex}"
                editor.insert(
                    "ai_signals",
                    {
                        "id": split_id,
                        "analysis_id": run_id,
                        "theme": source["theme"],
                        "classification": source["classification"],
                        "severity": source["severity"],
                        "summary": source["summary"],
                    },
                )
                editor.insert(
                    "voice_signal_details",
                    {
                        "signal_id": split_id,
                        **{
                            col: details[col]
                            for col in (
                                "theme_code",
                                "subtheme",
                                "state",
                                "original_json",
                                "priority_json",
                            )
                        },
                    },
                )
                split = _amend(editor, split_id, source, details, command, kept, sample, threshold)
                _review_event(
                    editor,
                    split_id,
                    "split_new",
                    "amended",
                    rationale,
                    {**split, "split_from": identity},
                )
                kept = {key: value for key, value in evidence.items() if key not in selected}
                command = command.model_copy(
                    update={
                        "theme": None,
                        "severity": None,
                        "classification": None,
                        "subtheme": None,
                    }
                )
            changes = _amend(editor, identity, source, details, command, kept, sample, threshold)
            _review_event(editor, identity, command.action, "amended", rationale, changes)
    return read_review(database, survey_id, run_id)


def create_action(
    database: Database, actor: AuditActor, identity: str, command: ActionCreate
) -> ReviewWorkspace:
    with database.transaction(write=True) as connection:
        editor = SourceEditor(
            connection, current_dataset(connection, command.expected_version()), actor
        )
        _, _, run = _current_signal(editor, identity)
        if not editor.get("gold_voice_published_findings", "id", identity):
            raise InvalidOperation(
                "Publish the reviewed finding before creating a management action."
            )
        today = datetime.now(UTC).date()
        if not today <= command.due_on <= today + timedelta(days=366):
            raise InvalidOperation("Choose an action due date in the coming year.")
        if connection.execute("SELECT COUNT(*) FROM voice_action_tracking").fetchone()[0] >= 60:
            raise InvalidOperation("This demo generation reached its action limit.")
        action_id = f"act-{uuid4().hex}"
        editor.insert(
            "management_actions",
            {
                "id": action_id,
                "signal_id": identity,
                "title": redact(command.title),
                "assigned_team": command.team,
                "status": "open",
                "due_on": command.due_on.isoformat(),
            },
        )
        editor.insert(
            "voice_action_tracking",
            {
                "id": action_id,
                "created_on": today.isoformat(),
                "baseline": redact(command.baseline),
                "target": redact(command.target),
                "expected_benefit": redact(command.expected_benefit),
            },
        )
        editor.audit(
            "voice_action",
            action_id,
            "create_action",
            None,
            {"signal_id": identity, "team": command.team, "due_on": command.due_on.isoformat()},
        )
    return read_review(database, run["survey_id"], run["id"])


def update_action(
    database: Database, actor: AuditActor, identity: str, command: ActionUpdate
) -> ReviewWorkspace:
    with database.transaction(write=True) as connection:
        editor = SourceEditor(
            connection, current_dataset(connection, command.expected_version()), actor
        )
        item = editor.require("management_actions", "id", identity, "Management action")
        editor.require("voice_action_tracking", "id", identity, "Management action")
        _, _, run = _current_signal(editor, item["signal_id"])
        if item["status"] == "closed" or (item["status"], command.status) == ("open", "closed"):
            raise InvalidOperation(
                "Start an open action before closing it. A closed action is final."
            )
        editor.update("management_actions", "id", identity, {"status": command.status})
        editor.update(
            "voice_action_tracking",
            "id",
            identity,
            {
                "notes": redact(command.notes),
                "closure_evidence": redact(command.closure_evidence)
                if command.closure_evidence
                else None,
            },
        )
        editor.audit(
            "voice_action",
            identity,
            "update_action",
            {"status": item["status"]},
            {"status": command.status, "closure_recorded": bool(command.closure_evidence)},
        )
    return read_review(database, run["survey_id"], run["id"])
