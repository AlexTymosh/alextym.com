"""Versioned synthetic report with explicitly labelled seeded review evidence."""

import sqlite3

from workforce_intelligence.surveys import link_evidence

SEED_VERSION = "1.1"
ANALYSIS_ID = "analysis-rota-001"
SURVEY_ID = "survey-rota-001"

_COMMENTS = (
    "Give the team a little more notice when the next week's rota changes.",
    "Short-notice rota swaps make it harder to plan handovers.",
    "A predictable rota and more time to recover after a change would help.",
    "Our regular handover check-in is useful and should continue.",
    "Publish a single rota update so the whole team sees the same changes.",
    "It would help to have protected time to recover after a run of shifts.",
    "Keep the monthly training slot and the clear booking process.",
    "Review the recovery time between closely spaced shifts.",
    "Tell us earlier when the published rota is revised.",
    "There should be one place to check why the rota changed.",
    None,
    None,
)


def populate_voice_report(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO survey_campaigns VALUES (?, ?, ?, ?, ?, ?)",
        (
            SURVEY_ID,
            "Rota Changes and Workforce Pressure",
            "What would help your team plan its work?",
            "2026-10-01",
            "2026-10-24",
            17,
        ),
    )
    connection.executemany(
        "INSERT INTO survey_responses VALUES (?, ?, ?, ?)",
        [
            (f"rota-{index:03d}", SURVEY_ID, f"2026-10-{index + 6:02d}", comment)
            for index, comment in enumerate(_COMMENTS, start=1)
        ],
    )
    connection.execute(
        "INSERT INTO ai_analyses VALUES (?, ?, ?, ?)",
        (ANALYSIS_ID, SURVEY_ID, "2026-10-26", "Demonstration fallback result"),
    )
    connection.executemany(
        "INSERT INTO ai_signals VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "signal-rota-001",
                ANALYSIS_ID,
                "Short-notice rota changes",
                "Concern",
                "Moderate signal",
                "Several fictional respondents asked for earlier or more consistent communication about rota changes.",
                "2026-10-28",
            ),
            (
                "signal-rota-002",
                ANALYSIS_ID,
                "Recovery time between shifts",
                "Suggestion",
                "Possible signal",
                "Some synthetic responses mention time to recover between shifts.",
                None,
            ),
        ],
    )
    link_evidence(
        connection,
        "signal-rota-001",
        ("rota-001", "rota-002", "rota-003", "rota-005", "rota-009", "rota-010"),
    )
    link_evidence(connection, "signal-rota-002", ("rota-003", "rota-006", "rota-008"))
    connection.execute(
        "INSERT INTO analyst_reviews VALUES (?, ?, ?, ?, ?, ?)",
        (
            "review-rota-001",
            "signal-rota-001",
            "confirmed",
            "Seeded demonstration review",
            "The six fictional comments explicitly discuss notice, planning, or communication about rota changes.",
            "2026-10-27",
        ),
    )
    connection.execute(
        "INSERT INTO management_actions VALUES (?, ?, ?, ?, ?, ?)",
        (
            "action-rota-001",
            "signal-rota-001",
            "Trial one weekly rota update and agree a minimum notice target",
            "Demo Workforce Planning",
            "Proposed",
            "2026-11-13",
        ),
    )
    connection.execute(
        """
        INSERT INTO audit_events (entity_type, entity_key, action, occurred_at, actor_uid,
             new_values, source_channel, correlation_id, demo_session_id)
        SELECT 'survey_analysis', ?, 'publish_seeded_fallback', refreshed_at, 'synthetic-seed',
             '{"review_kind":"seeded demonstration review"}', 'seed', 'seed:' || dataset_id,
             dataset_id || ':' || dataset_generation FROM dataset_state
        """,
        (ANALYSIS_ID,),
    )
