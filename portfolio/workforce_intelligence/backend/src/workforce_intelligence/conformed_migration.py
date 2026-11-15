"""Read-only, revision-current conformed Workforce dimensions and facts.

These logical SQLite views have no refresh job: every read reflects the same
transactional operational revision. Source events remain authoritative.
"""

CONFORMED_MIGRATION = (
    """
    CREATE VIEW dim_date AS
    WITH RECURSIVE days(day) AS (
        SELECT history_start FROM dataset_state
        UNION ALL
        SELECT date(day, '+1 day') FROM days
        WHERE day < (SELECT as_of_date FROM dataset_state)
    )
    SELECT day AS date_key, substr(day, 1, 7) AS month_key,
           date(day, 'start of month', '+1 month', '-1 day') AS calendar_month_end
    FROM days
    """,
    "CREATE VIEW dim_organisation AS SELECT id, label, active FROM organisational_units",
    "CREATE VIEW dim_location AS SELECT id, label, active FROM locations",
    "CREATE VIEW dim_role AS SELECT id, label, pay_band, active FROM roles",
    "CREATE VIEW dim_pay_band AS SELECT DISTINCT pay_band AS id FROM roles",
    "CREATE VIEW dim_recruitment_source AS SELECT id, label, active FROM recruitment_sources",
    "CREATE VIEW dim_campaign AS SELECT id, label, opened_on FROM recruitment_campaigns",
    """
    CREATE VIEW dim_employee AS
    SELECT e.id, e.is_featured_demo_employee, e.display_order,
           p.age_band, p.ethnicity_group, p.disability_status
    FROM employees e LEFT JOIN employee_profiles p ON p.employee_id = e.id
    """,
    """
    CREATE VIEW fact_employment_interval AS
    SELECT employment.employee_id, employment.line_id, employment.valid_from,
           employment.valid_to, employment.contracted_fte_milli,
           line.organisation_id, line.location_id, line.role_id, role.pay_band
    FROM silver_substantive_employment employment
    JOIN establishment_lines line ON line.id = employment.line_id
    JOIN roles role ON role.id = line.role_id
    """,
    """
    CREATE VIEW fact_employee_monthly_snapshot AS
    WITH RECURSIVE months(month_start) AS (
        SELECT date(history_start, 'start of month') FROM dataset_state
        UNION ALL
        SELECT date(month_start, '+1 month') FROM months
        WHERE date(month_start, '+1 month') <= (SELECT as_of_date FROM dataset_state)
    ),
    cutoffs AS (
        SELECT substr(month_start, 1, 7) AS month_key,
               MIN(date(month_start, '+1 month', '-1 day'), state.as_of_date) AS month_end
        FROM months CROSS JOIN dataset_state state
    )
    SELECT cutoffs.month_key, cutoffs.month_end, employment.employee_id,
           employment.line_id, employment.contracted_fte_milli,
           employment.organisation_id, employment.location_id,
           employment.role_id, employment.pay_band,
           state.dataset_id, state.dataset_generation, state.revision AS source_revision
    FROM cutoffs JOIN fact_employment_interval employment
      ON employment.valid_from <= cutoffs.month_end
     AND (employment.valid_to IS NULL OR employment.valid_to > cutoffs.month_end)
    CROSS JOIN dataset_state state
    """,
    """
    CREATE VIEW fact_vacancy AS
    SELECT vacancy.id, vacancy.line_id, line.organisation_id, line.location_id,
           line.role_id, role.pay_band, vacancy.campaign_id,
           vacancy.approved_positions, vacancy.approved_fte_milli,
           vacancy.requested_on, vacancy.approved_on, vacancy.advertised_on,
           vacancy.closed_on, vacancy.closure_kind, vacancy.over_establishment
    FROM bronze_vacancies vacancy
    JOIN establishment_lines line ON line.id = vacancy.line_id
    JOIN roles role ON role.id = line.role_id
    """,
    """
    CREATE VIEW fact_application AS
    SELECT application.id, application.vacancy_id, application.received_on,
           application.source_code, application.disposition, application.disposed_on,
           application.internal_employee_id, vacancy.campaign_id,
           vacancy.organisation_id, vacancy.location_id, vacancy.role_id, vacancy.pay_band
    FROM silver_applications application
    JOIN fact_vacancy vacancy ON vacancy.id = application.vacancy_id
    """,
    """
    CREATE VIEW fact_application_stage_event AS
    SELECT event.application_id, event.stage_code, event.occurred_on
    FROM silver_application_events event
    """,
    """
    CREATE VIEW fact_offer AS
    SELECT offer.id, offer.application_id, offer.vacancy_id,
           offer.offered_on, offer.resolved_on, offer.outcome
    FROM silver_offers offer
    """,
    """
    CREATE VIEW fact_new_starter AS
    SELECT starter.offer_id, starter.employee_id, starter.application_id,
           starter.vacancy_id, starter.started_on, starter.started_fte_milli
    FROM silver_starters starter
    """,
    """
    CREATE VIEW fact_leaver AS
    SELECT employee_id, leaving_date, reason FROM leaver_events
    """,
    """
    CREATE VIEW fact_internal_progression AS
    SELECT employee_id, occurred_on, from_line_id, to_line_id, kind
    FROM promotion_events
    """,
    """
    CREATE VIEW fact_learning AS
    SELECT id, employee_id, occurred_on, activity_code, completed FROM learning_events
    """,
    """
    CREATE VIEW fact_pdr AS
    SELECT id, employee_id, occurred_on, status FROM pdr_events
    """,
    """
    CREATE VIEW fact_probation AS
    SELECT employee_id, occurred_on, outcome FROM probation_events
    """,
)
