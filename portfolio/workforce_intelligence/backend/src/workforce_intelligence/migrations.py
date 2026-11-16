"""Forward-only, application-owned migrations in schema order."""

from workforce_intelligence.conformed_migration import CONFORMED_MIGRATION
from workforce_intelligence.forecast_migration import FORECAST_MIGRATION
from workforce_intelligence.operations_migration import (
    OPERATIONS_MIGRATION,
    OPERATIONS_TABLES,
)
from workforce_intelligence.projections import PROJECTION_MIGRATION
from workforce_intelligence.survey_migration import SURVEY_MIGRATION, SURVEY_TABLES
from workforce_intelligence.workbook_migration import WORKBOOK_MIGRATION
from workforce_intelligence.voice_migration import (
    VOICE_REVIEW_MIGRATION,
    VOICE_REVIEW_TABLES,
    VOICE_SOURCE_MIGRATION,
    VOICE_SOURCE_TABLES,
)

_TEMPORAL = """
    valid_from TEXT NOT NULL,
    valid_to TEXT CHECK (valid_to > valid_from),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    change_reason TEXT NOT NULL
"""

# These names are part of the schema, fixed at migration definition time.
_REFERENCES = ("organisational_units", "locations", "roles")


def _no_overlaps(table: str, key: str) -> tuple[str, str]:
    """Enforce half-open effective periods across all writes, including imports."""
    return tuple(
        f"""
        CREATE TRIGGER {table}_no_overlap_{operation.lower()}
        BEFORE {operation} ON {table}
        WHEN EXISTS (
            SELECT 1 FROM {table} AS existing
            WHERE existing.{key} = NEW.{key} {exclude_old}
              AND (existing.valid_to IS NULL OR NEW.valid_from < existing.valid_to)
              AND (NEW.valid_to IS NULL OR existing.valid_from < NEW.valid_to)
        )
        BEGIN
            SELECT RAISE(ABORT, 'Effective periods overlap');
        END
        """
        for operation, exclude_old in (
            ("INSERT", ""),
            ("UPDATE", "AND existing.id <> OLD.id"),
        )
    )


MIGRATIONS = (
    (
        """
        CREATE TABLE dataset_state (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            dataset_id TEXT NOT NULL,
            dataset_generation INTEGER NOT NULL CHECK (dataset_generation >= 1),
            revision INTEGER NOT NULL CHECK (revision >= 0),
            scenario_code TEXT NOT NULL,
            generation_seed INTEGER NOT NULL,
            seed_version TEXT NOT NULL,
            history_start TEXT NOT NULL,
            as_of_date TEXT NOT NULL CHECK (as_of_date >= history_start),
            generated_at TEXT NOT NULL,
            refreshed_at TEXT NOT NULL
        ) STRICT
        """,
        *(
            f"CREATE TABLE {table} (id TEXT PRIMARY KEY, label TEXT NOT NULL UNIQUE) STRICT"
            for table in _REFERENCES
        ),
        """
        CREATE TABLE establishment_lines (
            id TEXT PRIMARY KEY,
            organisation_id TEXT NOT NULL REFERENCES organisational_units(id),
            location_id TEXT NOT NULL REFERENCES locations(id),
            role_id TEXT NOT NULL REFERENCES roles(id),
            UNIQUE (organisation_id, location_id, role_id)
        ) STRICT
        """,
        f"""
        CREATE TABLE establishment_history (
            id INTEGER PRIMARY KEY,
            line_id TEXT NOT NULL REFERENCES establishment_lines(id),
            approved_positions INTEGER NOT NULL CHECK (approved_positions > 0),
            budget_fte_milli INTEGER NOT NULL CHECK (budget_fte_milli > 0),
            {_TEMPORAL},
            UNIQUE (line_id, valid_from)
        ) STRICT
        """,
        """
        CREATE TABLE employees (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            is_featured_demo_employee INTEGER NOT NULL CHECK (is_featured_demo_employee IN (0, 1)),
            display_order INTEGER UNIQUE,
            record_version INTEGER NOT NULL DEFAULT 1 CHECK (record_version >= 1),
            CHECK (
                (is_featured_demo_employee = 1 AND display_order IS NOT NULL AND display_order > 0)
                OR (is_featured_demo_employee = 0 AND display_order IS NULL)
            )
        ) STRICT
        """,
        f"""
        CREATE TABLE employment_contracts (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL REFERENCES employees(id),
            contracted_fte_milli INTEGER NOT NULL CHECK (contracted_fte_milli BETWEEN 1 AND 1000),
            is_substantive INTEGER NOT NULL CHECK (is_substantive IN (0, 1)),
            {_TEMPORAL},
            UNIQUE (employee_id, valid_from)
        ) STRICT
        """,
        f"""
        CREATE TABLE organisation_assignments (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL REFERENCES employees(id),
            line_id TEXT NOT NULL REFERENCES establishment_lines(id),
            {_TEMPORAL},
            UNIQUE (employee_id, valid_from)
        ) STRICT
        """,
        *_no_overlaps("establishment_history", "line_id"),
        *_no_overlaps("employment_contracts", "employee_id"),
        *_no_overlaps("organisation_assignments", "employee_id"),
        """
        CREATE TABLE vacancies (
            id TEXT PRIMARY KEY,
            line_id TEXT NOT NULL REFERENCES establishment_lines(id),
            title TEXT NOT NULL,
            approved_positions INTEGER NOT NULL CHECK (approved_positions > 0),
            approved_fte_milli INTEGER NOT NULL CHECK (approved_fte_milli > 0),
            approved_on TEXT NOT NULL,
            advertised_on TEXT CHECK (advertised_on >= approved_on),
            closed_on TEXT CHECK (closed_on >= COALESCE(advertised_on, approved_on)),
            closure_kind TEXT CHECK (closure_kind IN ('cancelled', 'administrative')),
            record_version INTEGER NOT NULL DEFAULT 1 CHECK (record_version >= 1),
            CHECK ((closed_on IS NULL) = (closure_kind IS NULL))
        ) STRICT
        """,
        """
        CREATE TABLE candidate_applications (
            id TEXT PRIMARY KEY,
            vacancy_id TEXT NOT NULL REFERENCES vacancies(id),
            received_on TEXT NOT NULL,
            source_code TEXT NOT NULL
        ) STRICT
        """,
        """
        CREATE TABLE application_stage_events (
            id INTEGER PRIMARY KEY,
            application_id TEXT NOT NULL REFERENCES candidate_applications(id),
            stage_code TEXT NOT NULL CHECK (stage_code IN (
                'screened', 'shortlisted', 'interviewed', 'checks_completed',
                'start_confirmed', 'probation_completed'
            )),
            occurred_on TEXT NOT NULL
        ) STRICT
        """,
        """
        CREATE TABLE offers (
            id TEXT PRIMARY KEY,
            application_id TEXT NOT NULL UNIQUE REFERENCES candidate_applications(id),
            offered_on TEXT NOT NULL,
            resolved_on TEXT CHECK (resolved_on >= offered_on),
            outcome TEXT CHECK (outcome IN ('accepted', 'declined', 'withdrawn')),
            CHECK ((resolved_on IS NULL) = (outcome IS NULL))
        ) STRICT
        """,
        """
        CREATE TABLE starter_events (
            offer_id TEXT PRIMARY KEY REFERENCES offers(id),
            employee_id TEXT NOT NULL UNIQUE REFERENCES employees(id),
            started_on TEXT NOT NULL,
            started_fte_milli INTEGER NOT NULL CHECK (started_fte_milli BETWEEN 1 AND 1000)
        ) STRICT
        """,
        """
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            action TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            actor_uid TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            source_channel TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            demo_session_id TEXT NOT NULL
        ) STRICT
        """,
        """
        CREATE TABLE reset_receipts (
            actor_uid TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            prior_generation INTEGER NOT NULL,
            reset_generation INTEGER NOT NULL,
            PRIMARY KEY (actor_uid, idempotency_key)
        ) STRICT
        """,
        "CREATE INDEX vacancies_approval ON vacancies (approved_on)",
        "CREATE INDEX applications_vacancy ON candidate_applications (vacancy_id)",
        "CREATE INDEX applications_cohort ON candidate_applications (received_on)",
        "CREATE INDEX stage_events_application ON application_stage_events (application_id, stage_code, occurred_on)",
        "CREATE INDEX starters_date ON starter_events (started_on)",
    ),
    PROJECTION_MIGRATION,
    SURVEY_MIGRATION,
    OPERATIONS_MIGRATION,
    (
        "ALTER TABLE reset_receipts ADD COLUMN request_kind TEXT NOT NULL DEFAULT 'reset'",
        """
        CREATE TABLE candidate_demographics (
            application_id TEXT PRIMARY KEY REFERENCES candidate_applications(id),
            age_band TEXT NOT NULL, ethnicity_group TEXT NOT NULL, disability_status TEXT NOT NULL
        ) STRICT
        """,
    ),
    WORKBOOK_MIGRATION,
    CONFORMED_MIGRATION,
    VOICE_SOURCE_MIGRATION,
    VOICE_REVIEW_MIGRATION,
    FORECAST_MIGRATION,
)

# Parent-first order, reversed when replacing the data within a transaction.
SOURCE_TABLES = (
    *_REFERENCES,
    "establishment_lines",
    "establishment_history",
    "employees",
    "employment_contracts",
    "organisation_assignments",
    "recruitment_sources",
    "recruitment_campaigns",
    "vacancies",
    "candidate_applications",
    "candidate_demographics",
    "application_stage_events",
    "offers",
    "starter_events",
    *OPERATIONS_TABLES,
    *SURVEY_TABLES,
    *VOICE_SOURCE_TABLES,
    *VOICE_REVIEW_TABLES,
    "import_batches",
    "forecast_runs",
    "forecast_results",
)
