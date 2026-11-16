"""Versioned, disposable Workforce forecasts and scenario evaluations."""

FORECAST_MIGRATION = (
    """
    CREATE TABLE forecast_runs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL CHECK (kind IN ('forecast', 'scenario')),
        model_version TEXT NOT NULL,
        dataset_id TEXT NOT NULL,
        dataset_generation INTEGER NOT NULL,
        source_revision INTEGER NOT NULL,
        cutoff TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('complete', 'insufficient_history')),
        inputs TEXT NOT NULL CHECK (json_valid(inputs)),
        result TEXT NOT NULL CHECK (json_valid(result)),
        created_at TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE forecast_results (
        run_id TEXT NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
        month_key TEXT NOT NULL,
        value REAL NOT NULL,
        baseline REAL NOT NULL,
        PRIMARY KEY (run_id, month_key)
    ) STRICT
    """,
    """
    CREATE VIEW fact_forecast AS
    SELECT r.run_id, r.month_key, r.value, r.baseline,
           json_extract(run.inputs, '$.metric') AS metric,
           run.cutoff, run.model_version, run.source_revision, run.dataset_generation
    FROM forecast_results r JOIN forecast_runs run ON run.id = r.run_id
    """,
)
