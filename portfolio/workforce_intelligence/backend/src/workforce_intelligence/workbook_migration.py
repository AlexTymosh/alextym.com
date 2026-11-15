"""Project-owned workbook staging and bounded rate receipts."""

WORKBOOK_MIGRATION = (
    """
    CREATE TABLE import_batches (
        id TEXT PRIMARY KEY,
        actor_uid TEXT NOT NULL,
        dataset_generation INTEGER NOT NULL,
        source_revision INTEGER NOT NULL,
        file_hash TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        preview_json TEXT NOT NULL,
        commands_json TEXT NOT NULL,
        last_failure_at INTEGER,
        receipt_json TEXT,
        UNIQUE (actor_uid, dataset_generation, source_revision, file_hash)
    ) STRICT
    """,
    """
    CREATE TABLE workbook_requests (
        id INTEGER PRIMARY KEY,
        operation TEXT NOT NULL,
        actor_uid TEXT NOT NULL,
        requested_at INTEGER NOT NULL
    ) STRICT
    """,
    "CREATE INDEX workbook_requests_time ON workbook_requests (requested_at)",
    "CREATE INDEX workbook_requests_scope ON workbook_requests (operation, actor_uid)",
)
