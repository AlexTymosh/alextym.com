"""Deterministic full-scale synthetic fixture. No staff or internal SCAS records."""

import sqlite3
from datetime import date
from random import Random

from workforce_intelligence.contracts import add_employment
from workforce_intelligence.dataset import SeedDefinition
from workforce_intelligence.directory_names import (
    FEATURED_NAMES,
    FULL_FEATURED_IDS,
    FULL_SEED_VERSION,
    synthetic_name,
)
from workforce_intelligence.seed import (
    AS_OF_DATE,
    INTERVIEW_SEED,
    SOURCE_TIMESTAMP,
    _application,
    populate_interview,
)
from workforce_intelligence.voice_campaigns import populate_candidate_feedback

HISTORY_START = date(2023, 11, 1)
EMPLOYEE_COUNT = 4400
MONTHS = 36
HIRES_PER_MONTH = 8
BASE_PEOPLE = EMPLOYEE_COUNT - 17 - MONTHS * HIRES_PER_MONTH
FEATURED_ORDER = {employee_id: order for order, employee_id in enumerate(FULL_FEATURED_IDS, 1)}
UNIT_LABELS = (
    "Patient Flow",
    "Integrated Care",
    "Preparedness",
    "Clinical Support",
    "Education",
    "Quality",
    "Operations Support",
    "Digital Services",
    "Business Support",
)
ROLE_LABELS = (
    "Responder",
    "Shift Lead",
    "Specialist Clinician",
    "Dispatcher",
    "Triage Advisor",
    "Transfer Assistant",
    "Clinical Educator",
    "Practice Lead",
    "Duty Coordinator",
    "Resource Planner",
    "Technical Analyst",
    "Driver Support",
    "Service Analyst",
    "Team Lead",
    "Care Navigator",
    "Fleet Technician",
    "Systems Engineer",
    "Clinical Auditor",
    "Service Coordinator",
    "Training Assistant",
    "Administrator",
    "Workforce Analyst",
    "Operations Manager",
    "Quality Advisor",
)
AGE_BANDS = ("18-24", "25-34", "35-44", "45-54", "55-64", "65-plus", "not-stated")
ETHNICITY_GROUPS = ("white", "mixed", "asian", "black", "other", "not-stated")
DISABILITY_GROUPS = ("no", "yes", "not-stated")
SOURCE_CODES = ("careers", "job-board", "referral", "outreach", "internal", "other")


def _day(month: int, day: int) -> str:
    index = HISTORY_START.year * 12 + HISTORY_START.month - 1 + month
    return date(index // 12, index % 12 + 1, day).isoformat()


def _reference_data(conn: sqlite3.Connection) -> list[str]:
    units = [(f"unit-{i:02}", f"Demo {label}") for i, label in enumerate(UNIT_LABELS, 1)]
    locations = [
        (f"base-{i:02}", f"Demo {region}{(i - 1) % 9 + 1:02} Base")
        for i in range(1, 34)
        for region in ["NWES"[(i - 1) // 9]]
    ]
    roles = [
        (f"role-{i:02}", f"Demo {label}", str(2 + i % 6)) for i, label in enumerate(ROLE_LABELS, 1)
    ]
    conn.executemany("INSERT INTO organisational_units (id, label) VALUES (?, ?)", units)
    conn.executemany("INSERT INTO locations (id, label) VALUES (?, ?)", locations)
    conn.executemany("INSERT INTO roles (id, label, pay_band) VALUES (?, ?, ?)", roles)
    lines = [
        (
            f"budget-{i + 1:02}",
            units[i % len(units)][0],
            locations[i % len(locations)][0],
            roles[(i * 7) % len(roles)][0],
        )
        for i in range(66)
    ]
    conn.executemany("INSERT INTO establishment_lines VALUES (?, ?, ?, ?)", lines)
    conn.executemany(
        """
        INSERT INTO establishment_history (line_id, approved_positions, budget_fte_milli,
            valid_from, valid_to, created_at, created_by, change_reason)
        VALUES (?, ?, ?, ?, ?, ?, 'synthetic-seed', 'synthetic_establishment')
        """,
        [
            (line[0], seats, fte, start, end, SOURCE_TIMESTAMP)
            for i, line in enumerate(lines)
            for seats, fte, start, end in (
                [
                    (68, 56000 + i % 5 * 1000, _day(0, 1), _day(17, 1)),
                    (70, 58000 + i % 5 * 1000, _day(17, 1), None),
                ]
                if i % 5 == 0
                else [(69, 58000 + i % 5 * 1000, _day(0, 1), None)]
            )
        ],
    )
    return [line[0] for line in lines]


def _demographics(random: Random) -> tuple[str, str, str]:
    return (
        random.choices(AGE_BANDS, (8, 22, 23, 21, 17, 4, 5))[0],
        random.choices(ETHNICITY_GROUPS, (66, 6, 10, 7, 4, 7))[0],
        random.choices(DISABILITY_GROUPS, (82, 9, 9))[0],
    )


def _employment(
    conn: sqlite3.Connection,
    random: Random,
    employee: str,
    line: str,
    start: str,
    fte: int,
    *,
    featured_order: int | None = None,
    temporary: bool = False,
    leave: str | None = None,
    leave_reason: str | None = None,
) -> None:
    add_employment(
        conn,
        employee_id=employee,
        display_name=FEATURED_NAMES[featured_order - 1]
        if featured_order
        else synthetic_name(employee),
        line_id=line,
        fte_milli=fte,
        start=start,
        created_at=SOURCE_TIMESTAMP,
        created_by="synthetic-seed",
        change_reason="synthetic_baseline",
        featured_order=featured_order,
        substantive=not temporary,
    )
    if leave:
        conn.execute(
            "UPDATE employment_contracts SET valid_to = ? WHERE employee_id = ?",
            (leave, employee),
        )
        conn.execute(
            "UPDATE organisation_assignments SET valid_to = ? WHERE employee_id = ?",
            (leave, employee),
        )
        conn.execute("INSERT INTO leaver_events VALUES (?, ?, ?)", (employee, leave, leave_reason))
    conn.execute(
        """
        INSERT INTO employee_profiles (employee_id, employment_status, leaving_date, leaving_reason,
                                       age_band, ethnicity_group, disability_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (employee, "Leaver" if leave else "Active", leave, leave_reason, *_demographics(random)),
    )


def _base_workforce(conn: sqlite3.Connection, random: Random, lines: list[str]) -> None:
    for index in range(BASE_PEOPLE):
        employee_id = f"demo-{index + 1:04}"
        line = lines[index % len(lines)]
        cohort = index % MONTHS
        leave = _day(cohort, 21) if index % 23 == 0 else None
        reason = (
            random.choice(("resignation", "retirement", "fixed_term_end", "other"))
            if leave
            else None
        )
        fte = random.choices((400, 600, 750, 800, 900, 1000), (1, 4, 5, 8, 12, 70))[0]
        temporary = index % 19 == 0
        _employment(
            conn,
            random,
            employee_id,
            line,
            date(
                random.randint(2008, 2023), random.randint(1, 10), random.randint(1, 28)
            ).isoformat(),
            fte,
            featured_order=FEATURED_ORDER.get(employee_id),
            temporary=temporary,
            leave=leave,
            leave_reason=reason,
        )
        revised_on = _day(cohort, 9)
        if index % 13 == 0:
            conn.execute(
                "UPDATE employment_contracts SET valid_to = ? WHERE employee_id = ?",
                (revised_on, employee_id),
            )
            conn.execute(
                """
                INSERT INTO employment_contracts (employee_id, contracted_fte_milli, is_substantive,
                    valid_from, valid_to, created_at, created_by, change_reason)
                VALUES (?, ?, ?, ?, ?, ?, 'synthetic-seed', 'synthetic_hours_change')
                """,
                (
                    employee_id,
                    800 if fte != 800 else 1000,
                    not temporary,
                    revised_on,
                    leave,
                    SOURCE_TIMESTAMP,
                ),
            )
        if index % 17 == 0:
            target = lines[(index + 1) % len(lines)]
            kind = ("promotion", "internal_appointment", "transfer")[(index // 17) % 3]
            conn.execute(
                "UPDATE organisation_assignments SET valid_to = ? WHERE employee_id = ?",
                (revised_on, employee_id),
            )
            conn.execute(
                """
                INSERT INTO organisation_assignments (employee_id, line_id, valid_from, valid_to,
                    created_at, created_by, change_reason) VALUES (?, ?, ?, ?, ?, 'synthetic-seed', ?)
                """,
                (employee_id, target, revised_on, leave, SOURCE_TIMESTAMP, kind),
            )
            if kind != "transfer":
                conn.execute(
                    "INSERT INTO promotion_events VALUES (?, ?, ?, ?, ?)",
                    (employee_id, revised_on, line, target, kind),
                )
        for period in range(cohort % 12, MONTHS, 12):
            event = _day(period, 14)
            if leave and event >= leave:
                continue
            conn.execute(
                "INSERT INTO pdr_events VALUES (?, ?, ?, ?)",
                (
                    f"pdr-{index}-{period}",
                    employee_id,
                    event,
                    random.choices(("completed", "due", "overdue"), (76, 16, 8))[0],
                ),
            )
            if index % 3 == 0:
                conn.execute(
                    "INSERT INTO learning_events VALUES (?, ?, ?, ?, ?)",
                    (
                        f"learn-{index}-{period}",
                        employee_id,
                        event,
                        random.choice(
                            ("induction", "clinical-skills", "safe-driving", "team-lead")
                        ),
                        int(random.random() > 0.1),
                    ),
                )
            if index % 7 == 0:
                conn.execute(
                    "INSERT INTO absence_events VALUES (?, ?, ?, ?)",
                    (f"absence-{index}-{period}", employee_id, event, random.randint(1, 6)),
                )


def _recruitment(conn: sqlite3.Connection, random: Random, lines: list[str]) -> None:
    for month in range(MONTHS):
        campaign_id = f"intake-{month + 1:02}"
        conn.execute(
            "INSERT INTO recruitment_campaigns VALUES (?, ?, ?)",
            (campaign_id, f"Demo recruitment {month + 1:02}", _day(month, 1)),
        )
        for slot in range(12):
            _vacancy(
                conn, random, lines[(month * 11 + slot * 7) % len(lines)], month, slot, campaign_id
            )


def _vacancy(
    conn: sqlite3.Connection,
    random: Random,
    line: str,
    month: int,
    slot: int,
    campaign: str,
) -> None:
    key = f"{month + 1:02}-{slot + 1:02}"
    vacancy = f"opening-{key}"
    fte = random.choice((750, 800, 1000, 1000))
    closed = (
        "cancelled"
        if slot == 9 or (slot == 8 and month < MONTHS - 3)
        else "administrative"
        if slot == 10 or (slot == 11 and month < MONTHS - 3)
        else None
    )
    approved = _day(month, 2)
    conn.execute(
        """
        INSERT INTO vacancies (id, line_id, title, approved_positions, approved_fte_milli,
           requested_on, approved_on, advertised_on, closed_on, closure_kind, campaign_id)
        VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vacancy,
            line,
            f"Demo opening {key}",
            fte,
            _day(month, 1),
            approved,
            _day(month, 3),
            _day(month, 28) if closed else None,
            closed,
            campaign,
        ),
    )
    for index in range(random.randint(5, 9)):
        _candidate(conn, random, vacancy, line, fte, month, slot, index, key)


def _candidate(
    conn: sqlite3.Connection,
    random: Random,
    vacancy: str,
    line: str,
    fte: int,
    month: int,
    slot: int,
    index: int,
    key: str,
) -> None:
    application = f"candidate-{key}-{index + 1:02}"
    offer = f"conditional-{key}-{index + 1:02}"
    stages = {}
    if index < 5 or random.random() < 0.5:
        stages["screened"] = _day(month, 7)
    if index < 3:
        stages["shortlisted"] = _day(month, 8)
        stages["interviewed"] = _day(month, 10 + index)
    _application(
        conn,
        application,
        vacancy,
        _day(month, random.randint(4, 6)),
        random.choices(SOURCE_CODES, (45, 23, 12, 8, 9, 3))[0],
        **stages,
    )
    conn.execute(
        "INSERT INTO candidate_demographics VALUES (?, ?, ?, ?)",
        (application, *_demographics(random)),
    )
    if index < 3:
        conn.execute(
            "INSERT INTO interviews VALUES (?, ?, ?)",
            (application, stages["interviewed"], "passed" if index <= 1 else "unsuccessful"),
        )
    if index == 2:
        conn.execute(
            "UPDATE candidate_applications SET disposition = 'rejected', disposed_on = ? WHERE id = ?",
            (stages["interviewed"], application),
        )
    if index == 1 and (slot == 10 or random.random() < 0.24):
        conn.execute(
            "INSERT INTO offers VALUES (?, ?, ?, ?, ?)",
            (
                offer,
                application,
                _day(month, 13),
                _day(month, 16),
                random.choice(("declined", "withdrawn")),
            ),
        )
    if index != 0 or slot == 8 or slot == 10:
        return
    conn.execute(
        "INSERT INTO offers VALUES (?, ?, ?, ?, 'accepted')",
        (offer, application, _day(month, 12), _day(month, 15)),
    )
    conn.execute(
        "INSERT INTO pre_employment_checks (offer_id, checked_on, status) VALUES (?, ?, 'pending')",
        (offer, _day(month, 16)),
    )
    check = "failed" if slot == 9 else "passed"
    conn.execute(
        "INSERT INTO pre_employment_checks (offer_id, checked_on, status) VALUES (?, ?, ?)",
        (offer, _day(month, 18), check),
    )
    if check == "failed":
        conn.execute(
            "UPDATE candidate_applications SET disposition = 'withdrawn', disposed_on = ? WHERE id = ?",
            (_day(month, 19), application),
        )
        return
    actual = _day(month, 23 + (slot + month) % 5)
    planned = _day(month, 24) if slot < HIRES_PER_MONTH else _day(month + 1, 6)
    conn.execute(
        "UPDATE candidate_applications SET planned_start_on = ? WHERE id = ?",
        (planned, application),
    )
    conn.executemany(
        "INSERT INTO application_stage_events (application_id, stage_code, occurred_on) VALUES (?, ?, ?)",
        [
            (application, "checks_completed", _day(month, 18)),
            (application, "start_confirmed", _day(month, 21)),
        ],
    )
    if slot >= HIRES_PER_MONTH:
        return
    employee = f"hire-{key}"
    _employment(conn, random, employee, line, actual, fte)
    conn.execute("INSERT INTO starter_events VALUES (?, ?, ?, ?)", (offer, employee, actual, fte))
    if month + 2 < MONTHS:
        outcome = random.choices(("passed", "extended", "unsuccessful"), (86, 11, 3))[0]
        probation = _day(month + 2, 24)
        conn.execute(
            "INSERT INTO probation_events VALUES (?, ?, ?)", (employee, probation, outcome)
        )
        if outcome != "extended":
            conn.execute(
                "INSERT INTO application_stage_events (application_id, stage_code, occurred_on) VALUES (?, 'probation_completed', ?)",
                (application, probation),
            )


VOICE_COMMENTS = (
    "Synthetic comment: clearer handover notes would help when the rota changes.",
    "Synthetic comment: protected development time would make training easier to attend.",
    "Synthetic comment: the new team check-ins have helped me raise small issues sooner.",
    "Synthetic comment: shifts have been busier and recovery time has felt tighter.",
    "Synthetic comment: local leads give useful feedback after a difficult shift.",
    None,
)


def _listening(conn: sqlite3.Connection, random: Random) -> None:
    for month in range(MONTHS):
        survey = f"pulse-{month + 1:02}"
        conn.execute(
            "INSERT INTO survey_campaigns VALUES (?, ?, ?, ?, ?, ?)",
            (
                survey,
                f"Demo workforce pulse {month + 1:02}",
                "What helped or made work harder this month?",
                _day(month, 1),
                _day(month, 26),
                random.randint(430, 590),
            ),
        )
        conn.executemany(
            "INSERT INTO survey_responses VALUES (?, ?, ?, ?)",
            [
                (
                    f"{survey}-{index:03}",
                    survey,
                    _day(month, random.randint(3, 25)),
                    random.choices(VOICE_COMMENTS, (14, 10, 16, 10 + month % 11, 11, 32))[0],
                )
                for index in range(random.randint(110, 215))
            ],
        )


def _populate(connection: sqlite3.Connection, seed: int) -> None:
    populate_interview(connection, INTERVIEW_SEED.generation_seed, full_fixture=True)
    random = Random(seed)
    lines = _reference_data(connection)
    _base_workforce(connection, random, lines)
    _recruitment(connection, random, lines)
    _listening(connection, random)
    populate_candidate_feedback(connection)


FULL_SEED = SeedDefinition(
    "full-controlled", 424400, FULL_SEED_VERSION, HISTORY_START, AS_OF_DATE, _populate
)
