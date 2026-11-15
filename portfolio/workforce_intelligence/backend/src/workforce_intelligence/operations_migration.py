"""Additional source tables and metadata for the operational lifecycle."""

REFERENCE_TABLES = ("organisational_units", "locations", "roles")
RECRUITMENT_SOURCES = (
    "careers",
    "job-board",
    "referral",
    "outreach",
    "internal",
    "other",
)

OPERATIONS_MIGRATION = (
    *(
        f"ALTER TABLE {table} ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))"
        for table in REFERENCE_TABLES
    ),
    "ALTER TABLE roles ADD COLUMN pay_band TEXT NOT NULL DEFAULT 'Not specified'",
    """
    CREATE TABLE employee_profiles (
        employee_id TEXT PRIMARY KEY REFERENCES employees(id),
        employment_status TEXT NOT NULL DEFAULT 'Active' CHECK (employment_status IN ('Active', 'Leaver')),
        leaving_date TEXT,
        leaving_reason TEXT,
        age_band TEXT NOT NULL DEFAULT 'not-stated',
        ethnicity_group TEXT NOT NULL DEFAULT 'not-stated',
        disability_status TEXT NOT NULL DEFAULT 'not-stated',
        CHECK ((employment_status = 'Leaver') = (leaving_date IS NOT NULL AND leaving_reason IS NOT NULL))
    ) STRICT
    """,
    "ALTER TABLE vacancies ADD COLUMN requested_on TEXT",
    "ALTER TABLE vacancies ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 1 CHECK (is_approved IN (0, 1))",
    """
    ALTER TABLE vacancies ADD COLUMN over_establishment INTEGER NOT NULL DEFAULT 0
        CHECK (over_establishment IN (0, 1))
    """,
    "ALTER TABLE vacancies ADD COLUMN over_establishment_reason TEXT",
    """
    CREATE TABLE recruitment_campaigns (
        id TEXT PRIMARY KEY, label TEXT NOT NULL, opened_on TEXT NOT NULL
    ) STRICT
    """,
    "ALTER TABLE vacancies ADD COLUMN campaign_id TEXT REFERENCES recruitment_campaigns(id)",
    """
    CREATE TABLE recruitment_sources (
        id TEXT PRIMARY KEY, label TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
    ) STRICT
    """,
    "ALTER TABLE candidate_applications ADD COLUMN record_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE candidate_applications ADD COLUMN disposition TEXT CHECK (disposition IN ('withdrawn', 'rejected'))",
    "ALTER TABLE candidate_applications ADD COLUMN disposed_on TEXT",
    "ALTER TABLE candidate_applications ADD COLUMN planned_start_on TEXT",
    "ALTER TABLE candidate_applications ADD COLUMN internal_employee_id TEXT REFERENCES employees(id)",
    """
    CREATE TABLE interviews (
        application_id TEXT PRIMARY KEY REFERENCES candidate_applications(id),
        interviewed_on TEXT NOT NULL, outcome TEXT NOT NULL CHECK (outcome IN ('passed', 'unsuccessful'))
    ) STRICT
    """,
    """
    CREATE TABLE pre_employment_checks (
        id INTEGER PRIMARY KEY, offer_id TEXT NOT NULL REFERENCES offers(id), checked_on TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('pending', 'passed', 'failed')),
        UNIQUE (offer_id, checked_on)
    ) STRICT
    """,
    """
    CREATE TABLE probation_events (
        employee_id TEXT NOT NULL REFERENCES employees(id),
        occurred_on TEXT NOT NULL, outcome TEXT NOT NULL CHECK (outcome IN ('passed', 'extended', 'unsuccessful')),
        PRIMARY KEY (employee_id, occurred_on)
    ) STRICT
    """,
    """
    CREATE TABLE learning_events (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(id),
        occurred_on TEXT NOT NULL, activity_code TEXT NOT NULL, completed INTEGER NOT NULL CHECK (completed IN (0, 1))
    ) STRICT
    """,
    """
    CREATE TABLE pdr_events (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(id),
        occurred_on TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('due', 'completed', 'overdue'))
    ) STRICT
    """,
    """
    CREATE TABLE promotion_events (
        employee_id TEXT NOT NULL REFERENCES employees(id), occurred_on TEXT NOT NULL,
        from_line_id TEXT NOT NULL REFERENCES establishment_lines(id),
        to_line_id TEXT NOT NULL REFERENCES establishment_lines(id),
        kind TEXT NOT NULL CHECK (kind IN ('promotion', 'internal_appointment')),
        PRIMARY KEY (employee_id, occurred_on)
    ) STRICT
    """,
    """
    CREATE TABLE leaver_events (
        employee_id TEXT PRIMARY KEY REFERENCES employees(id), leaving_date TEXT NOT NULL, reason TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE absence_events (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(id),
        started_on TEXT NOT NULL, days INTEGER NOT NULL CHECK (days BETWEEN 1 AND 31)
    ) STRICT
    """,
    "CREATE INDEX learning_employee ON learning_events (employee_id, occurred_on)",
    "CREATE INDEX pdr_employee ON pdr_events (employee_id, occurred_on)",
    "CREATE INDEX absence_employee ON absence_events (employee_id, started_on)",
    # Preserve the original projection migrations. A draft is a request, never an approved
    # vacancy or a denominator. Replacing only this view keeps Silver dependencies intact.
    "DROP VIEW bronze_vacancies",
    """
    CREATE VIEW bronze_vacancies AS
    SELECT source.*, state.dataset_id, state.dataset_generation, state.revision AS source_revision
    FROM vacancies AS source CROSS JOIN dataset_state AS state WHERE source.is_approved = 1
    """,
    *(
        f"INSERT INTO recruitment_sources (id, label) VALUES ('{code}', '{code.replace('-', ' ').title()}')"
        for code in RECRUITMENT_SOURCES
    ),
    """
    INSERT INTO interviews
    SELECT event.application_id, MIN(event.occurred_on), 'passed'
    FROM application_stage_events event JOIN offers ON offers.application_id = event.application_id
    WHERE event.stage_code = 'interviewed' GROUP BY event.application_id
    """,
    """
    INSERT INTO pre_employment_checks (offer_id, checked_on, status)
    SELECT offers.id, MIN(event.occurred_on), 'passed'
    FROM application_stage_events event JOIN offers ON offers.application_id = event.application_id
    WHERE event.stage_code = 'checks_completed' GROUP BY offers.id
    """,
)

OPERATIONS_TABLES = (
    "employee_profiles",
    "interviews",
    "pre_employment_checks",
    "probation_events",
    "learning_events",
    "pdr_events",
    "promotion_events",
    "leaver_events",
    "absence_events",
)
