"""Bounded external classification, validated evidence and recoverable demo runs."""

import json
import logging
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, Literal, Protocol
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    InvalidOperation,
    current_dataset,
    record_audit,
)
from workforce_intelligence.operation_store import SourceEditor
from workforce_intelligence.schemas import DatasetRequest, DatasetResponse, EntityId
from workforce_intelligence.voice_analytics import SEVERITY, priority, protected, ratio
from workforce_intelligence.voice_campaigns import campaign
from workforce_intelligence.voice_taxonomy import CLASSIFICATIONS, QUESTION_BANK, SEVERITIES, THEMES

PROMPT_VERSION = "voice-classification-3"
MAX_AI_COMMENTS = 60
MAX_AI_SIGNALS = 12
MAX_EXCERPT_LENGTH = 140
MAX_RUNS = 80
MAX_EXTERNAL_RUNS = 20
EXTERNAL_COOLDOWN = 15
Theme = Literal[*THEMES]
Classification = Literal[*CLASSIFICATIONS]
Severity = Literal[*SEVERITIES]
Compact = Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=320)]
logger = logging.getLogger(__name__)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_id: EntityId
    excerpt: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=6, max_length=MAX_EXCERPT_LENGTH)
    ]


class SignalClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Theme
    subtheme: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=80)] | None
    )
    classification: Classification
    severity: Severity
    summary: Compact
    priority_human_review: bool


class ClassifiedSignal(SignalClassification):
    evidence: Annotated[list[EvidenceItem], Field(min_length=1, max_length=MAX_AI_COMMENTS)]
    unique_response_count: Annotated[int, Field(strict=True, ge=1, le=MAX_AI_COMMENTS)]


class ClassifiedReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: Compact
    signals: Annotated[list[ClassifiedSignal], Field(max_length=MAX_AI_SIGNALS)]


class AnalyseRequest(DatasetRequest):
    mode: Literal["ai", "demo"]
    idempotency_key: UUID


class RunResponse(DatasetResponse):
    run: dict


class VoiceProviderTimeout(RuntimeError):
    """The external classifier did not respond before its deadline."""


class VoiceProvider(Protocol):
    name: str
    model: str

    def classify(self, question: str, comments: list[dict[str, str]]) -> ClassifiedReport:
        """Return a structured report. Never approve or publish a finding."""
        ...


def get_voice_provider(request: Request) -> VoiceProvider | None:
    return getattr(request.app.state, "workforce_voice_provider", None)


_IDENTIFIERS = (
    (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]"),
    (r"(?:https?://|www\.)\S+", "[link removed]"),
    (r"(?<!\w)(?:\+?\d[\d(). -]{6,}\d)(?!\w)", "[number removed]"),
    (r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", "[postcode removed]"),
    (r"\b(?:Dr|Mr|Mrs|Ms|Miss|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", "[name removed]"),
    (r"\b(?:emp(?:loyee)?|staff|patient|nhs)[ -]?(?:id[ :#-]*)?\d[\w-]*\b", "[identifier removed]"),
    (
        r"\b\d+\s+(?:[A-Za-z]+\s+){1,4}(?:Street|Road|Drive|Lane|Avenue|Court)\b",
        "[address removed]",
    ),
)
_NAMES = re.compile(r"(?<![.!?]\s)\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b")


def redact(text: str) -> str:
    for pattern, substitute in _IDENTIFIERS:
        text = re.sub(pattern, substitute, text, flags=re.IGNORECASE)
    text = _NAMES.sub("[name removed]", text)
    return " ".join(text.split())


def validate_evidence(value: ClassifiedReport, comments: dict[str, str]) -> ClassifiedReport:
    report = ClassifiedReport.model_validate(value)
    seen = set()
    for signal in report.signals:
        if signal.theme in seen:
            raise InvalidOperation("The analysis returned duplicate theme signals.")
        seen.add(signal.theme)
        keys = {row.response_id for row in signal.evidence}
        if len(keys) != len(signal.evidence) or len(keys) != signal.unique_response_count:
            raise InvalidOperation("The declared response count does not match distinct evidence.")
        for row in signal.evidence:
            if row.response_id not in comments or row.excerpt not in comments[row.response_id]:
                raise InvalidOperation("The analysis cited an unknown response or excerpt.")
        signal.summary = redact(signal.summary)
        signal.subtheme = redact(signal.subtheme) if signal.subtheme else None
    report.summary = redact(report.summary)
    return report


def _comments(connection, survey_id: str) -> dict[str, str]:
    rows = connection.execute(
        """SELECT r.id, r.comment FROM survey_responses r JOIN voice_response_context c ON r.id = c.response_id
        WHERE r.survey_id = ? AND r.comment IS NOT NULL""",
        (survey_id,),
    ).fetchall()
    # Bounded deterministic sample; the report explicitly uses this sample as its denominator.
    rows = sorted(rows, key=lambda row: sha256(row["id"].encode()).digest())
    return {row["id"]: clean for row in rows[:MAX_AI_COMMENTS] if (clean := redact(row["comment"]))}


def _demo_result(connection, comments: dict[str, str]) -> ClassifiedReport:
    by_theme = defaultdict(list)
    marks = [
        row
        for row in connection.execute(
            """SELECT response_id, theme, classification, severity, excerpt FROM survey_response_themes
        WHERE response_id IN (SELECT value FROM json_each(?)) ORDER BY response_id, sentence_number""",
            (json.dumps(list(comments)),),
        )
    ]
    for mark in marks:
        by_theme[mark["theme"]].append(mark)
    signals = []
    for theme, items in sorted(by_theme.items(), key=lambda item: (-len(item[1]), item[0])):
        selected = {
            item["response_id"]: EvidenceItem(
                response_id=item["response_id"], excerpt=redact(item["excerpt"])
            )
            for item in items
            if redact(item["excerpt"]) in comments[item["response_id"]]
        }
        if not selected:
            continue
        worst = max(items, key=lambda row: SEVERITY[row["severity"]])
        signals.append(
            ClassifiedSignal(
                theme=theme,
                subtheme=None,
                classification=worst["classification"],
                severity=worst["severity"],
                summary=f"Synthetic responses mention {THEMES[theme].lower()}. Review the supplied excerpts.",
                evidence=list(selected.values()),
                unique_response_count=len(selected),
                priority_human_review=theme in ("safety", "speaking-up")
                or worst["severity"] == "Critical",
            )
        )
    return ClassifiedReport(
        summary="Demonstration classifications use the known synthetic source labels. Human review is required.",
        signals=signals[:MAX_AI_SIGNALS],
    )


def _run_card(run) -> dict:
    response_ids = json.loads(run["response_ids"])
    return {
        "id": run["id"],
        "status": run["status"],
        "mode": run["mode"],
        "provider": run["provider"],
        "model": run["model"],
        "started_at": run["started_at"],
        "completed_at": run["completed_at"],
        "taxonomy_version": run["taxonomy_version"],
        "prompt_version": run["prompt_version"],
        "input_hash": run["input_hash"],
        "sample_size": len(response_ids),
        "supersedes": run["supersedes"],
        "failure": run["failure"],
        "label": "Demonstration fallback result"
        if run["mode"] == "demo"
        else "External AI analysis",
    }


def _finish(
    editor: SourceEditor, run, info: dict, report: ClassifiedReport | None, failure: str | None
):
    run_id = run["id"]
    now = editor.prepare().refreshed_at
    if report is not None:
        editor.insert(
            "ai_analyses",
            {
                "id": run_id,
                "survey_id": run["survey_id"],
                "analysed_on": now,
                "analysis_label": _run_card(run)["label"],
            },
        )
        sample = len(json.loads(run["response_ids"]))
        for i, signal in enumerate(report.signals, 1):
            identity = f"{run_id}-s{i}"
            editor.insert(
                "ai_signals",
                {
                    "id": identity,
                    "analysis_id": run_id,
                    "theme": THEMES[signal.theme],
                    "classification": signal.classification,
                    "severity": signal.severity,
                    "summary": signal.summary,
                },
            )
            prevalence = (
                None
                if protected(sample, signal.unique_response_count, info["anonymity_min"])
                else ratio(signal.unique_response_count, sample)
            )
            score = priority(
                signal.theme,
                signal.severity,
                prevalence,
                serious=signal.priority_human_review or signal.classification == "Safety concern",
            )
            editor.insert(
                "voice_signal_details",
                {
                    "signal_id": identity,
                    "theme_code": signal.theme,
                    "subtheme": signal.subtheme,
                    "state": "awaiting_review",
                    "original_json": signal.model_dump_json(),
                    "priority_json": json.dumps(score),
                },
            )
            for evidence in signal.evidence:
                editor.insert(
                    "survey_signal_evidence",
                    {"signal_id": identity, "response_id": evidence.response_id},
                )
                editor.insert(
                    "voice_evidence_spans", {"signal_id": identity, **evidence.model_dump()}
                )
    editor.update(
        "voice_analysis_runs",
        "id",
        run_id,
        {
            "status": "ready" if report is not None else "failed",
            "completed_at": now,
            "result_json": report.model_dump_json() if report is not None else None,
            "failure": failure,
        },
    )
    record_audit(
        editor.connection,
        editor.state,
        editor.actor,
        entity_type="survey_analysis",
        entity_key=run_id,
        action="analyse_synthetic_fallback" if run["mode"] == "demo" else "analyse_with_provider",
        old_values=None,
        new_values={
            "status": "ready" if report else "failed",
            "provider": run["provider"],
            "input_hash": run["input_hash"],
            "signal_count": len(report.signals) if report else 0,
            "failure": failure,
        },
    )
    logger.info(
        "Workforce analysis %s status=%s model=%s prompt_version=%s failure=%s request_id=%s",
        run_id,
        "ready" if report is not None else "failed",
        run["model"],
        run["prompt_version"],
        failure,
        editor.actor.correlation_id,
    )
    return RunResponse(
        dataset=editor.state, run=_run_card(editor.get("voice_analysis_runs", "id", run_id))
    )


def run_analysis(
    database: Database,
    actor: AuditActor,
    survey_id: str,
    command: AnalyseRequest,
    provider: VoiceProvider | None,
) -> RunResponse:
    run_id = f"va-{uuid4().hex}"
    expected = command.expected_version()
    with database.transaction(write=True) as connection:
        state = current_dataset(connection, expected)
        info = campaign(connection, survey_id)
        editor = SourceEditor(connection, state, actor)
        key = str(command.idempotency_key)
        ticket = connection.execute(
            "SELECT * FROM voice_analysis_runs WHERE survey_id = ? AND request_key = ?",
            (survey_id, key),
        ).fetchone()
        if ticket:
            if ticket["mode"] != command.mode:
                raise Conflict("This analysis key was used for a different mode.")
            return RunResponse(dataset=state, run=_run_card(ticket))
        now = datetime.now(UTC)
        stale = (now - timedelta(seconds=60)).isoformat()
        connection.execute(
            "UPDATE voice_analysis_runs SET status = 'failed', completed_at = ?, failure = 'interrupted' "
            "WHERE status = 'running' AND started_at < ?",
            (now.isoformat(), stale),
        )
        if connection.execute(
            "SELECT 1 FROM voice_analysis_runs WHERE survey_id = ? AND status = 'running'",
            (survey_id,),
        ).fetchone():
            raise Conflict("An analysis is already running for this campaign.")
        if connection.execute("SELECT COUNT(*) FROM voice_analysis_runs").fetchone()[0] >= MAX_RUNS:
            raise InvalidOperation("This demo generation reached its analysis limit.")
        if command.mode == "ai":
            recent_cutoff = (now - timedelta(seconds=EXTERNAL_COOLDOWN)).isoformat()
            count, recent = connection.execute(
                "SELECT COUNT(*), MAX(started_at) FROM voice_analysis_runs WHERE mode = 'ai'"
            ).fetchone()
            if count >= MAX_EXTERNAL_RUNS or recent and recent > recent_cutoff:
                raise InvalidOperation(
                    "Duplicate or frequent external requests are limited. Wait before trying again."
                )
        comments = _comments(connection, survey_id)
        if len(comments) < info["anonymity_min"]:
            raise InvalidOperation(
                "Generate enough analysable synthetic comments to meet the anonymity minimum."
            )
        # Custom questions can contain arbitrary text. Only the controlled question bank leaves the app.
        approved_questions = {
            question["prompt"] for question in QUESTION_BANK if question["kind"] == "comment"
        }
        question = (
            info["question"]
            if info["question"] in approved_questions
            else QUESTION_BANK[0]["prompt"]
        )
        previous = connection.execute(
            "SELECT id FROM voice_analysis_runs WHERE survey_id = ? ORDER BY started_at DESC LIMIT 1",
            (survey_id,),
        ).fetchone()
        fingerprint = sha256(json.dumps([question, comments], sort_keys=True).encode()).hexdigest()
        editor.insert(
            "voice_analysis_runs",
            {
                "id": run_id,
                "survey_id": survey_id,
                "request_key": key,
                "mode": command.mode,
                "status": "running",
                "started_at": now.isoformat(),
                "provider": "synthetic-fixture"
                if command.mode == "demo"
                else provider.name
                if provider
                else "OpenAI",
                "model": "synthetic-labels-1"
                if command.mode == "demo"
                else provider.model
                if provider
                else "not-configured",
                "prompt_version": PROMPT_VERSION,
                "taxonomy_version": info["taxonomy_version"],
                "generation_seed": info["generation_seed"],
                "input_hash": fingerprint,
                "response_ids": json.dumps(list(comments)),
                "requested_by": actor.uid,
                "supersedes": previous[0] if previous else None,
            },
        )
        if command.mode == "demo":
            run = editor.get("voice_analysis_runs", "id", run_id)
            return _finish(
                editor,
                run,
                info,
                validate_evidence(_demo_result(connection, comments), comments),
                None,
            )
    report, failure = None, None
    try:
        if provider is None:
            failure = "provider_not_configured"
        else:
            raw = provider.classify(
                question,
                [
                    {"response_id": identity, "comment": comment}
                    for identity, comment in comments.items()
                ],
            )
            report = validate_evidence(raw, comments)
    except (InvalidOperation, ValidationError):
        failure = "evidence_validation_failed"
    except VoiceProviderTimeout:
        failure = "provider_timeout"
    except RuntimeError:
        failure = "provider_unavailable"
    with database.transaction(write=True) as connection:
        state = current_dataset(connection, expected)
        editor = SourceEditor(connection, state, actor)
        run = editor.require("voice_analysis_runs", "id", run_id, "Analysis")
        if run["status"] != "running":
            return RunResponse(dataset=state, run=_run_card(run))
        return _finish(editor, run, info, report, failure)
