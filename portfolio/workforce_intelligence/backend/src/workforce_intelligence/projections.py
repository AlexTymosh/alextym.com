"""SQLite source-grain and conformed views used by the MVP analytical queries."""

BRONZE_SOURCES = (
    "establishment_history",
    "employment_contracts",
    "organisation_assignments",
    "vacancies",
    "candidate_applications",
    "application_stage_events",
    "offers",
    "starter_events",
)

PROJECTION_MIGRATION = (
    *(
        f"""
        CREATE VIEW bronze_{table} AS
        SELECT source.*, state.dataset_id, state.dataset_generation, state.revision AS source_revision
        FROM {table} AS source CROSS JOIN dataset_state AS state
        """
        for table in BRONZE_SOURCES
    ),
    """
    CREATE VIEW silver_substantive_employment AS
    SELECT contract.employee_id, assignment.line_id, contract.contracted_fte_milli,
           MAX(contract.valid_from, assignment.valid_from) AS valid_from,
           CASE
               WHEN contract.valid_to IS NULL THEN assignment.valid_to
               WHEN assignment.valid_to IS NULL THEN contract.valid_to
               ELSE MIN(contract.valid_to, assignment.valid_to)
           END AS valid_to
    FROM bronze_employment_contracts AS contract
    JOIN bronze_organisation_assignments AS assignment
      ON assignment.employee_id = contract.employee_id
     AND (contract.valid_to IS NULL OR assignment.valid_from < contract.valid_to)
     AND (assignment.valid_to IS NULL OR contract.valid_from < assignment.valid_to)
    WHERE contract.is_substantive = 1
    """,
    """
    CREATE VIEW silver_applications AS
    SELECT app.* FROM bronze_candidate_applications AS app
    JOIN bronze_vacancies AS vacancy ON vacancy.id = app.vacancy_id
    WHERE app.received_on >= COALESCE(vacancy.advertised_on, vacancy.approved_on)
      AND (vacancy.closed_on IS NULL OR app.received_on <= vacancy.closed_on)
    """,
    """
    CREATE VIEW silver_offers AS
    SELECT offer.*, app.vacancy_id FROM bronze_offers AS offer
    JOIN silver_applications AS app ON app.id = offer.application_id
    WHERE offer.offered_on >= app.received_on
    """,
    """
    CREATE VIEW silver_starters AS
    SELECT starter.*, offer.vacancy_id, offer.application_id
    FROM bronze_starter_events AS starter
    JOIN silver_offers AS offer ON offer.id = starter.offer_id
    JOIN bronze_vacancies AS vacancy ON vacancy.id = offer.vacancy_id
    JOIN silver_substantive_employment AS employment ON employment.employee_id = starter.employee_id
      AND employment.line_id = vacancy.line_id AND employment.valid_from <= starter.started_on
      AND (employment.valid_to IS NULL OR employment.valid_to > starter.started_on)
    WHERE offer.outcome = 'accepted' AND starter.started_on >= offer.resolved_on
      AND (vacancy.closed_on IS NULL OR starter.started_on <= vacancy.closed_on)
    """,
    """
    CREATE VIEW silver_application_events AS
    SELECT id AS application_id, 'received' AS stage_code, received_on AS occurred_on
    FROM silver_applications
    UNION ALL
    SELECT event.application_id, event.stage_code, event.occurred_on
    FROM bronze_application_stage_events AS event
    JOIN silver_applications AS app ON app.id = event.application_id
    WHERE event.occurred_on >= app.received_on
    UNION ALL
    SELECT application_id, 'conditional_offer', offered_on FROM silver_offers
    UNION ALL
    SELECT application_id, 'offer_accepted', resolved_on FROM silver_offers WHERE outcome = 'accepted'
    UNION ALL
    SELECT application_id, 'started', started_on FROM silver_starters
    """,
)
