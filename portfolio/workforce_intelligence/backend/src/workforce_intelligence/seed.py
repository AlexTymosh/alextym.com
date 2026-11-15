"""Controlled interview data. All people and operational events are fictional."""

import sqlite3
from datetime import date
from random import Random

from workforce_intelligence.contracts import add_employment
from workforce_intelligence.dataset import SeedDefinition

HISTORY_START = date(2026, 7, 1)
AS_OF_DATE = date(2026, 10, 31)
SOURCE_TIMESTAMP = "2026-10-31T00:00:00+00:00"


def _populate(connection: sqlite3.Connection, generation_seed: int) -> None:
    connection.executemany(
        "INSERT INTO organisational_units VALUES (?, ?)",
        [
            ("response", "Demo Emergency Response"),
            ("control", "Demo Contact Centre"),
            ("transport", "Demo Patient Transport"),
        ],
    )
    connection.executemany(
        "INSERT INTO locations VALUES (?, ?)",
        [("west", "Demo West Base"), ("central", "Demo Central Hub"), ("east", "Demo East Base")],
    )
    connection.executemany(
        "INSERT INTO roles VALUES (?, ?)",
        [
            ("clinician", "Response clinician"),
            ("advisor", "Call advisor"),
            ("crew", "Transport crew"),
        ],
    )
    lines = [
        ("line-1", "response", "west", "clinician", 8),
        ("line-2", "control", "central", "advisor", 7),
        ("line-3", "transport", "east", "crew", 6),
    ]
    connection.executemany(
        "INSERT INTO establishment_lines VALUES (?, ?, ?, ?)", [line[:4] for line in lines]
    )
    connection.executemany(
        """
        INSERT INTO establishment_history (line_id, approved_positions, budget_fte_milli,
            valid_from, created_at, created_by, change_reason)
        VALUES (?, ?, ?, ?, ?, 'synthetic-seed', 'demo_baseline')
        """,
        [
            (line_id, positions, positions * 1000, HISTORY_START.isoformat(), SOURCE_TIMESTAMP)
            for line_id, _, _, _, positions in lines
        ],
    )

    random = Random(generation_seed)
    for order, letter in enumerate("ABCDEFGHIJKLMNO", start=1):
        employee_id = f"emp-{order:03d}"
        line_id = lines[(order - 1) // 5][0]
        fte = 1000 if order in (1, 3) else random.choice((600, 800, 1000))
        _employee(
            connection,
            employee_id,
            f"Demo {letter}.",
            line_id,
            fte,
            HISTORY_START.isoformat(),
            featured_order=order,
        )
    connection.execute("""
        UPDATE employment_contracts SET valid_to = '2026-08-15' WHERE employee_id = 'emp-003'
    """)
    connection.execute(
        """
        INSERT INTO employment_contracts (employee_id, contracted_fte_milli, is_substantive,
            valid_from, created_at, created_by, change_reason)
        VALUES ('emp-003', 600, 1, '2026-08-15', ?, 'synthetic-seed', 'demo_hours_change')
        """,
        (SOURCE_TIMESTAMP,),
    )

    connection.executemany(
        """
        INSERT INTO vacancies (id, line_id, title, approved_positions, approved_fte_milli,
            approved_on, advertised_on, closed_on, closure_kind)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "vac-001",
                "line-1",
                "Response intake",
                1,
                1000,
                "2026-09-01",
                "2026-09-03",
                None,
                None,
            ),
            (
                "vac-002",
                "line-2",
                "Cancelled advisor intake",
                1,
                1000,
                "2026-09-11",
                "2026-09-13",
                "2026-10-03",
                "cancelled",
            ),
            (
                "vac-003",
                "line-2",
                "Advisor intake",
                1,
                1000,
                "2026-10-01",
                "2026-10-02",
                None,
                None,
            ),
            (
                "vac-004",
                "line-3",
                "Transport intake",
                2,
                1800,
                "2026-08-26",
                "2026-08-29",
                None,
                None,
            ),
            (
                "vac-005",
                "line-1",
                "Response reserve intake",
                1,
                1000,
                "2026-09-25",
                "2026-09-27",
                "2026-10-15",
                "administrative",
            ),
            (
                "vac-006",
                "line-1",
                "Response outreach intake",
                1,
                1000,
                "2026-10-04",
                "2026-10-06",
                None,
                None,
            ),
        ],
    )
    # The four dated recruitment facts are distinct sources: application,
    # stage events, offer decision and actual start.
    _application(
        connection,
        "app-001",
        "vac-001",
        "2026-09-06",
        "careers",
        screened="2026-09-07",
        shortlisted="2026-09-11",
        interviewed="2026-09-15",
        checks_completed="2026-09-28",
        start_confirmed="2026-10-01",
    )
    _application(connection, "app-002", "vac-001", "2026-09-07", "job-board", screened="2026-09-08")
    _application(
        connection,
        "app-003",
        "vac-002",
        "2026-09-15",
        "careers",
        screened="2026-09-16",
        shortlisted="2026-09-18",
        interviewed="2026-09-19",
    )
    _application(
        connection,
        "app-004",
        "vac-003",
        "2026-10-04",
        "careers",
        screened="2026-10-05",
        shortlisted="2026-10-09",
        interviewed="2026-10-12",
        checks_completed="2026-10-21",
        start_confirmed="2026-10-23",
    )
    _application(
        connection,
        "app-005",
        "vac-003",
        "2026-10-06",
        "job-board",
        screened="2026-10-07",
        shortlisted="2026-10-10",
        interviewed="2026-10-13",
    )
    _application(
        connection,
        "app-006",
        "vac-004",
        "2026-09-02",
        "referral",
        screened="2026-09-04",
        shortlisted="2026-09-08",
        interviewed="2026-09-12",
        checks_completed="2026-09-20",
        start_confirmed="2026-09-22",
    )
    _application(
        connection,
        "app-007",
        "vac-005",
        "2026-10-01",
        "careers",
        screened="2026-10-02",
        shortlisted="2026-10-04",
        interviewed="2026-10-08",
    )
    _application(connection, "app-008", "vac-006", "2026-10-08", "outreach")
    _application(
        connection,
        "app-009",
        "vac-006",
        "2026-10-11",
        "outreach",
        screened="2026-10-12",
        shortlisted="2026-10-15",
        interviewed="2026-10-20",
    )
    connection.execute("""
        INSERT INTO application_stage_events (application_id, stage_code, occurred_on)
        VALUES ('app-004', 'screened', '2026-10-06')
    """)
    connection.executemany(
        "INSERT INTO offers (id, application_id, offered_on, resolved_on, outcome) VALUES (?, ?, ?, ?, ?)",
        [
            ("offer-001", "app-001", "2026-09-17", "2026-09-20", "accepted"),
            ("offer-002", "app-004", "2026-10-14", "2026-10-16", "accepted"),
            ("offer-003", "app-005", "2026-10-15", None, None),
            ("offer-004", "app-006", "2026-09-13", "2026-09-16", "accepted"),
            ("offer-005", "app-007", "2026-10-10", "2026-10-12", "withdrawn"),
            ("offer-006", "app-009", "2026-10-21", "2026-10-23", "declined"),
        ],
    )
    for offer, line, start, fte in [
        ("offer-001", "line-1", "2026-10-09", 1000),
        ("offer-004", "line-3", "2026-09-27", 800),
    ]:
        employee = f"starter-{offer}"
        _employee(connection, employee, f"Demo Starter {offer[-3:]}.", line, fte, start)
        connection.execute(
            "INSERT INTO starter_events VALUES (?, ?, ?, ?)", (offer, employee, start, fte)
        )


def _employee(
    connection: sqlite3.Connection,
    employee_id: str,
    name: str,
    line_id: str,
    fte: int,
    start: str,
    *,
    featured_order: int | None = None,
) -> None:
    add_employment(
        connection,
        employee_id=employee_id,
        display_name=name,
        line_id=line_id,
        fte_milli=fte,
        start=start,
        created_at=SOURCE_TIMESTAMP,
        created_by="synthetic-seed",
        change_reason="demo_baseline",
        featured_order=featured_order,
    )


def _application(
    connection: sqlite3.Connection,
    application_id: str,
    vacancy_id: str,
    received_on: str,
    source: str,
    **stages: str,
) -> None:
    connection.execute(
        "INSERT INTO candidate_applications VALUES (?, ?, ?, ?)",
        (application_id, vacancy_id, received_on, source),
    )
    connection.executemany(
        "INSERT INTO application_stage_events (application_id, stage_code, occurred_on) VALUES (?, ?, ?)",
        [(application_id, stage, occurred_on) for stage, occurred_on in stages.items()],
    )


INTERVIEW_SEED = SeedDefinition("interview-core", 1733, "1.0", HISTORY_START, AS_OF_DATE, _populate)
