"""Bounded management reads. Report projections keep their own cutoffs."""

import json
import sqlite3
from typing import Literal

from workforce_intelligence.dataset import RecordNotFound

Section = Literal[
    "vacancies",
    "candidates",
    "offers",
    "starters",
    "learning",
    "leavers",
    "references",
    "audit",
]

_LISTS = {
    "vacancies": """
        WITH fills AS (
            SELECT vacancy_id, COUNT(*) AS positions, SUM(started_fte_milli) AS wte
            FROM silver_starters GROUP BY vacancy_id
        )
        SELECT v.id, v.title, v.line_id, v.campaign_id, v.requested_on,
               CASE WHEN v.is_approved = 1 THEN v.approved_on END AS approved_on,
               v.advertised_on, v.closed_on, v.approved_positions,
               v.approved_fte_milli / 1000.0 AS approved_wte,
               COALESCE(f.positions, 0) AS filled_positions,
               COALESCE(f.wte, 0) / 1000.0 AS filled_wte,
               CASE WHEN v.is_approved = 0 THEN 'draft'
                    WHEN v.closure_kind = 'cancelled' THEN 'cancelled'
                    WHEN v.closed_on IS NOT NULL THEN 'closed'
                    WHEN f.positions >= v.approved_positions AND f.wte >= v.approved_fte_milli THEN 'filled'
                    WHEN f.positions > 0 THEN 'partially_filled'
                    WHEN v.advertised_on IS NOT NULL THEN 'advertised' ELSE 'approved' END AS status,
               v.over_establishment_reason AS exception_reason, v.record_version
        FROM vacancies v LEFT JOIN fills f ON f.vacancy_id = v.id
        ORDER BY COALESCE(v.requested_on, v.approved_on) DESC, v.id
    """,
    "candidates": """
        WITH progress AS (
            SELECT application_id, MAX(CASE stage_code WHEN 'screened' THEN 1 WHEN 'shortlisted' THEN 2
                WHEN 'interviewed' THEN 3 WHEN 'checks_completed' THEN 4 WHEN 'start_confirmed' THEN 5
                WHEN 'probation_completed' THEN 6 ELSE 0 END) AS level
            FROM application_stage_events GROUP BY application_id
        )
        SELECT app.id, app.vacancy_id, app.received_on, app.source_code, app.planned_start_on,
               app.record_version, i.outcome AS interview_outcome,
               CASE WHEN p.level = 6 THEN 'probation_completed'
                    WHEN starter.offer_id IS NOT NULL THEN 'started'
                    WHEN app.disposition IS NOT NULL THEN app.disposition
                    WHEN p.level = 5 THEN 'start_confirmed' WHEN p.level = 4 THEN 'checks_completed'
                    WHEN o.outcome IS NOT NULL THEN 'offer_' || o.outcome
                    WHEN o.id IS NOT NULL THEN 'conditional_offer'
                    WHEN p.level = 3 THEN 'interviewed'
                    WHEN p.level = 2 THEN 'shortlisted' WHEN p.level = 1 THEN 'screened'
                    ELSE 'received' END AS status
        FROM candidate_applications app LEFT JOIN progress p ON p.application_id = app.id
        LEFT JOIN interviews i ON i.application_id = app.id
        LEFT JOIN offers o ON o.application_id = app.id
        LEFT JOIN starter_events starter ON starter.offer_id = o.id
        ORDER BY app.received_on DESC, app.id
    """,
    "offers": """
        SELECT o.id, o.application_id, a.vacancy_id, o.offered_on, o.resolved_on,
               COALESCE(o.outcome, 'conditional') AS outcome,
               (SELECT status FROM pre_employment_checks c WHERE c.offer_id = o.id
                ORDER BY c.checked_on DESC LIMIT 1) AS check_status, a.planned_start_on
        FROM offers o JOIN candidate_applications a ON a.id = o.application_id
        ORDER BY o.offered_on DESC, o.id
    """,
    "starters": """
        SELECT s.employee_id, s.offer_id, s.started_on, s.started_fte_milli / 1000.0 AS fte,
               (SELECT outcome FROM probation_events p WHERE p.employee_id = s.employee_id
                ORDER BY p.occurred_on DESC LIMIT 1) AS probation
        FROM starter_events s ORDER BY s.started_on DESC, s.employee_id
    """,
    "learning": """
        SELECT * FROM (
            SELECT id, employee_id, occurred_on, 'learning' AS kind, activity_code,
                   CASE completed WHEN 1 THEN 'completed' ELSE 'scheduled' END AS status
            FROM learning_events
            UNION ALL
            SELECT id, employee_id, occurred_on, 'PDR' AS kind, NULL AS activity_code, status FROM pdr_events
        ) ORDER BY occurred_on DESC, kind, id
    """,
    "leavers": """
        SELECT l.employee_id, e.display_name, l.leaving_date, l.reason
        FROM leaver_events l JOIN employees e ON e.id = l.employee_id
        ORDER BY l.leaving_date DESC, l.employee_id
    """,
    "references": """
        SELECT * FROM (
            SELECT id, label, active, 'organisation' AS kind, NULL AS pay_band FROM organisational_units
            UNION ALL SELECT id, label, active, 'location', NULL FROM locations
            UNION ALL SELECT id, label, active, 'role', pay_band FROM roles
            UNION ALL SELECT id, label, active, 'recruitment_source', NULL FROM recruitment_sources
            UNION ALL SELECT id, label, 1, 'campaign', NULL FROM recruitment_campaigns
        ) ORDER BY kind, id
    """,
    "audit": """
        SELECT id, entity_type, entity_key, action, occurred_at, source_channel, correlation_id,
               old_values, new_values
        FROM audit_events ORDER BY id DESC
    """,
}


def read_section(connection: sqlite3.Connection, section: Section, limit: int, offset: int):
    rows = connection.execute(_LISTS[section] + " LIMIT ? OFFSET ?", (limit + 1, offset)).fetchall()
    return [dict(row) for row in rows[:limit]], offset + limit if len(rows) > limit else None


def establishment_options(connection: sqlite3.Connection, as_of: str, limit: int, offset: int):
    rows = connection.execute(
        """
        SELECT l.id, u.label || ' / ' || loc.label || ' / ' || r.label AS label,
                h.approved_positions, h.budget_fte_milli / 1000.0 AS budgeted_wte
        FROM establishment_lines l JOIN organisational_units u ON u.id = l.organisation_id AND u.active = 1
        JOIN locations loc ON loc.id = l.location_id AND loc.active = 1
        JOIN roles r ON r.id = l.role_id AND r.active = 1
        JOIN establishment_history h ON h.line_id = l.id AND h.valid_from <= :as_of
          AND (h.valid_to IS NULL OR h.valid_to > :as_of)
        ORDER BY l.id LIMIT :limit OFFSET :offset
        """,
        {"as_of": as_of, "limit": limit + 1, "offset": offset},
    ).fetchall()
    return [dict(row) for row in rows[:limit]], offset + limit if len(rows) > limit else None


def employee_details(connection: sqlite3.Connection, employee_id: str, day: str) -> dict:
    row = connection.execute(
        """
        SELECT e.id, e.display_name, e.record_version, p.leaving_date, p.leaving_reason,
               CASE WHEN p.leaving_date <= :day THEN 'Leaver'
                    WHEN c.id IS NOT NULL THEN 'Active' ELSE 'Inactive' END AS employment_status
        FROM employees e LEFT JOIN employee_profiles p ON p.employee_id = e.id
        LEFT JOIN employment_contracts c ON c.employee_id = e.id AND c.valid_from <= :day
          AND (c.valid_to IS NULL OR c.valid_to > :day)
        WHERE e.id = :identity
        """,
        {"day": day, "identity": employee_id},
    ).fetchone()
    if row is None:
        raise RecordNotFound("Employee not found.")
    contracts = connection.execute(
        """
        SELECT valid_from, valid_to, valid_to IS NULL AS is_current,
               contracted_fte_milli / 1000.0 AS contracted_fte, is_substantive, change_reason
        FROM employment_contracts WHERE employee_id = ? ORDER BY valid_from DESC LIMIT 200
        """,
        (employee_id,),
    )
    assignments = connection.execute(
        """
        SELECT a.valid_from, a.valid_to, a.valid_to IS NULL AS is_current, a.line_id,
               u.label AS organisation, loc.label AS location, r.label AS role, r.pay_band, a.change_reason
        FROM organisation_assignments a JOIN establishment_lines l ON l.id = a.line_id
        JOIN organisational_units u ON u.id = l.organisation_id
        JOIN locations loc ON loc.id = l.location_id JOIN roles r ON r.id = l.role_id
        WHERE a.employee_id = ? ORDER BY a.valid_from DESC LIMIT 200
        """,
        (employee_id,),
    )
    return {
        **dict(row),
        "as_of_date": day,
        "contracts": [dict(c) for c in contracts],
        "assignments": [dict(a) for a in assignments],
    }


def audit_values(rows: list[dict]) -> list[dict]:
    return [
        {
            **row,
            **{
                key: json.loads(row[key]) if row[key] else None
                for key in ("old_values", "new_values")
            },
        }
        for row in rows
    ]
