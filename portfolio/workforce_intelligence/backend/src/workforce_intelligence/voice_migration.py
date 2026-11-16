"""Generated survey sources kept alongside the existing interview report."""

VOICE_SOURCE_MIGRATION = (
    """
    CREATE TABLE voice_campaign_settings (
        survey_id TEXT PRIMARY KEY REFERENCES survey_campaigns(id),
        audience TEXT NOT NULL CHECK (audience IN ('employees', 'new_starters', 'exit')),
        organisation_id TEXT REFERENCES organisational_units(id),
        series TEXT NOT NULL,
        anonymity_min INTEGER NOT NULL CHECK (anonymity_min BETWEEN 5 AND 30),
        taxonomy_version TEXT NOT NULL,
        eligible INTEGER NOT NULL,
        generated_at TEXT,
        generation_seed INTEGER,
        generation_mode TEXT,
        generation_parameters TEXT,
        population_revision INTEGER
    ) STRICT
    """,
    """
    CREATE TABLE survey_questions (
        survey_id TEXT NOT NULL REFERENCES voice_campaign_settings(survey_id),
        code TEXT NOT NULL, prompt TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('comment', 'rating')),
        scale_max INTEGER, position INTEGER NOT NULL,
        PRIMARY KEY (survey_id, code)
    ) STRICT
    """,
    """
    CREATE TABLE voice_population (
        survey_id TEXT NOT NULL REFERENCES voice_campaign_settings(survey_id),
        dimension TEXT NOT NULL, category TEXT NOT NULL,
        eligible INTEGER NOT NULL CHECK (eligible > 0), invited INTEGER NOT NULL CHECK (invited >= 0),
        CHECK (invited <= eligible), PRIMARY KEY (survey_id, dimension, category)
    ) STRICT
    """,
    """
    CREATE TABLE voice_response_context (
        response_id TEXT PRIMARY KEY REFERENCES survey_responses(id),
        segments TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE voice_rating_responses (
        response_id TEXT NOT NULL REFERENCES survey_responses(id),
        question_code TEXT NOT NULL, rating INTEGER CHECK (rating BETWEEN 1 AND 7),
        PRIMARY KEY (response_id, question_code)
    ) STRICT
    """,
    """
    CREATE TABLE survey_response_themes (
        response_id TEXT NOT NULL REFERENCES survey_responses(id),
        sentence_number INTEGER NOT NULL CHECK (sentence_number > 0),
        theme TEXT NOT NULL, classification TEXT NOT NULL, severity TEXT NOT NULL, excerpt TEXT NOT NULL,
        PRIMARY KEY (response_id, sentence_number)
    ) STRICT
    """,
    "CREATE INDEX voice_campaign_series ON voice_campaign_settings (series, audience, organisation_id)",
)

VOICE_SOURCE_TABLES = (
    "voice_campaign_settings",
    "survey_questions",
    "voice_population",
    "voice_response_context",
    "voice_rating_responses",
    "survey_response_themes",
)

VOICE_REVIEW_MIGRATION = (
    """
    CREATE TABLE voice_analysis_runs (
        id TEXT PRIMARY KEY, survey_id TEXT NOT NULL REFERENCES voice_campaign_settings(survey_id),
        request_key TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('running', 'ready', 'failed')),
        started_at TEXT NOT NULL, completed_at TEXT, provider TEXT NOT NULL, model TEXT NOT NULL,
        prompt_version TEXT NOT NULL, taxonomy_version TEXT NOT NULL, generation_seed INTEGER,
        input_hash TEXT NOT NULL, response_ids TEXT NOT NULL, result_json TEXT, failure TEXT,
        supersedes TEXT, requested_by TEXT NOT NULL, UNIQUE (survey_id, request_key)
    ) STRICT
    """,
    """
    CREATE TABLE voice_signal_details (
        signal_id TEXT PRIMARY KEY REFERENCES ai_signals(id), theme_code TEXT NOT NULL, subtheme TEXT,
        state TEXT NOT NULL CHECK (state IN ('awaiting_review', 'confirmed', 'amended', 'rejected', 'published')),
        original_json TEXT NOT NULL, priority_json TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE voice_evidence_spans (
        signal_id TEXT NOT NULL, response_id TEXT NOT NULL, excerpt TEXT NOT NULL,
        PRIMARY KEY (signal_id, response_id),
        FOREIGN KEY (signal_id, response_id) REFERENCES survey_signal_evidence(signal_id, response_id)
    ) STRICT
    """,
    """
    CREATE TABLE voice_review_events (
        id INTEGER PRIMARY KEY, signal_id TEXT NOT NULL REFERENCES voice_signal_details(signal_id),
        action TEXT NOT NULL, rationale TEXT NOT NULL, actor TEXT NOT NULL, occurred_at TEXT NOT NULL, changes_json TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE voice_action_tracking (
        id TEXT PRIMARY KEY REFERENCES management_actions(id), created_on TEXT NOT NULL,
        baseline TEXT NOT NULL, target TEXT NOT NULL, expected_benefit TEXT NOT NULL,
        notes TEXT, closure_evidence TEXT
    ) STRICT
    """,
    "CREATE INDEX voice_runs_by_survey ON voice_analysis_runs(survey_id, started_at DESC)",
    """
    CREATE VIEW gold_voice_published_findings AS
    SELECT gold.*, detail.theme_code, detail.subtheme
    FROM gold_reviewed_survey_findings gold
    JOIN voice_signal_details detail ON detail.signal_id = gold.id AND detail.state = 'published'
    JOIN voice_analysis_runs run ON run.id = gold.analysis_id AND run.status = 'ready'
    JOIN voice_campaign_settings campaign ON campaign.survey_id = run.survey_id
    WHERE (SELECT COUNT(*) FROM voice_evidence_spans WHERE signal_id = gold.id) >= campaign.anonymity_min
      AND json_array_length(run.response_ids) >= campaign.anonymity_min
      AND (json_array_length(run.response_ids) = (SELECT COUNT(*) FROM voice_evidence_spans WHERE signal_id = gold.id)
        OR json_array_length(run.response_ids) - (SELECT COUNT(*) FROM voice_evidence_spans WHERE signal_id = gold.id)
          >= campaign.anonymity_min)
    """,
)
VOICE_REVIEW_TABLES = (
    "voice_analysis_runs",
    "voice_signal_details",
    "voice_evidence_spans",
    "voice_review_events",
    "voice_action_tracking",
)
