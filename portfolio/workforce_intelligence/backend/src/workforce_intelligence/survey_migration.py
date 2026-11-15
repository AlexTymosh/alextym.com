"""Add the controlled People Voice source and published-finding projection."""

import sqlite3
from datetime import UTC, datetime

from workforce_intelligence.survey_fixture import SEED_VERSION, populate_voice_report

SURVEY_TABLES = (
    "survey_campaigns",
    "survey_responses",
    "ai_analyses",
    "ai_signals",
    "survey_signal_evidence",
    "analyst_reviews",
    "management_actions",
)


def _add_report_to_existing_dataset(connection: sqlite3.Connection) -> None:
    updated = connection.execute(
        """
        UPDATE dataset_state SET revision = revision + 1, seed_version = ?, refreshed_at = ?
        WHERE scenario_code = 'interview-core'
        """,
        (SEED_VERSION, datetime.now(UTC).isoformat()),
    )
    if updated.rowcount:
        populate_voice_report(connection)


SURVEY_MIGRATION = (
    """
    CREATE TABLE survey_campaigns (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, question TEXT NOT NULL,
        period_start TEXT NOT NULL, period_end TEXT NOT NULL CHECK (period_end >= period_start),
        invited INTEGER NOT NULL CHECK (invited > 0)
    ) STRICT
    """,
    """
    CREATE TABLE survey_responses (
        id TEXT PRIMARY KEY, survey_id TEXT NOT NULL REFERENCES survey_campaigns(id),
        submitted_on TEXT NOT NULL, comment TEXT CHECK (comment IS NULL OR length(trim(comment)) > 0)
    ) STRICT
    """,
    """
    CREATE TABLE ai_analyses (
        id TEXT PRIMARY KEY, survey_id TEXT NOT NULL REFERENCES survey_campaigns(id),
        analysed_on TEXT NOT NULL, analysis_label TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE ai_signals (
        id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL REFERENCES ai_analyses(id), theme TEXT NOT NULL,
        classification TEXT NOT NULL, severity TEXT NOT NULL, summary TEXT NOT NULL, published_on TEXT
    ) STRICT
    """,
    """
    CREATE TABLE survey_signal_evidence (
        signal_id TEXT NOT NULL REFERENCES ai_signals(id),
        response_id TEXT NOT NULL REFERENCES survey_responses(id),
        PRIMARY KEY (signal_id, response_id)
    ) STRICT
    """,
    """
    CREATE TABLE analyst_reviews (
        id TEXT PRIMARY KEY, signal_id TEXT NOT NULL UNIQUE REFERENCES ai_signals(id),
        decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'amended', 'rejected')),
        review_kind TEXT NOT NULL, review_rationale TEXT NOT NULL, reviewed_on TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE management_actions (
        id TEXT PRIMARY KEY, signal_id TEXT NOT NULL REFERENCES ai_signals(id), title TEXT NOT NULL,
        assigned_team TEXT NOT NULL, status TEXT NOT NULL, due_on TEXT NOT NULL
    ) STRICT
    """,
    "CREATE INDEX survey_responses_campaign ON survey_responses (survey_id)",
    """
    CREATE VIEW gold_reviewed_survey_findings AS
    SELECT signal.*, review.review_kind, review.review_rationale, review.reviewed_on
    FROM ai_signals AS signal JOIN analyst_reviews AS review ON review.signal_id = signal.id
    JOIN ai_analyses AS analysis ON analysis.id = signal.analysis_id
    WHERE review.decision IN ('confirmed', 'amended')
      AND review.reviewed_on >= analysis.analysed_on AND signal.published_on >= review.reviewed_on
      AND EXISTS (SELECT 1 FROM survey_signal_evidence WHERE signal_id = signal.id)
      AND NOT EXISTS (
          SELECT 1 FROM survey_signal_evidence AS evidence JOIN survey_responses AS response
            ON response.id = evidence.response_id WHERE evidence.signal_id = signal.id
            AND (response.survey_id <> analysis.survey_id OR response.comment IS NULL)
      )
    """,
    _add_report_to_existing_dataset,
)
