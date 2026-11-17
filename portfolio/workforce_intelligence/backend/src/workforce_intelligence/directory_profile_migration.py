"""Directory titles and departments for the featured simulation profiles."""

import sqlite3

# In the same order as the featured directory. The flags identify inferred values.
_PROFILES = (
    (
        "Senior Management Information Analyst",
        "Digital and Data - Data and Analytics",
        False,
        False,
    ),
    (
        "Deputy Chief People Officer & Director of People & Education",
        "People and Education",
        False,
        True,
    ),
    ("Head of Data, Analytics and Insight", "Digital and Data - Data and Analytics", False, True),
    (None, "Digital and Data - Strategy and Development", False, False),
    ("Interim Managing Director", "Executive Management", False, True),
    (
        "Assistant Director of Digital Business Enablement",
        "Digital and Data - Product and Delivery",
        False,
        False,
    ),
    ("Business Analyst", "Digital and Data - Product and Delivery", False, False),
    ("Group Chair", "Board and Governance", False, True),
    (
        "Associate Director of Education and Professional Development",
        "People and Education - Education and Professional Development",
        False,
        True,
    ),
    ("Recruitment Manager", "People and Education - Recruitment", True, True),
    (None, "People and Education - Recruitment", False, True),
    (
        "People Engagement and Experience Manager",
        "People and Education - Engagement and Experience",
        False,
        True,
    ),
    (None, "People and Education - Engagement and Experience", False, True),
    (None, "People and Education", False, True),
    ("Analyst", "Digital and Data", False, False),
    ("Workforce Systems Advisor", "People and Education - Workforce Systems", False, True),
    ("Senior IM&T Manager", "Digital and Data - Product and Delivery", False, False),
    ("Senior SQL Database Administrator", "Digital and Data - IT Operations", False, False),
    ("IT Service Delivery Manager", "Digital and Data - IT Operations", False, False),
    ("Recruitment Co-ordinator", "People and Education - Recruitment", False, True),
)


def seed_directory_profiles(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO featured_directory_profiles VALUES (?, ?, ?, ?, ?)",
        [(position, *profile) for position, profile in enumerate(_PROFILES, start=1)],
    )


DIRECTORY_PROFILE_MIGRATION = (
    """
    CREATE TABLE featured_directory_profiles (
        display_order INTEGER PRIMARY KEY CHECK (display_order > 0),
        job_title TEXT,
        department TEXT NOT NULL,
        title_inferred INTEGER NOT NULL CHECK (title_inferred IN (0, 1)),
        department_inferred INTEGER NOT NULL CHECK (department_inferred IN (0, 1)),
        CHECK (title_inferred = 0 OR job_title IS NOT NULL)
    ) STRICT
    """,
    seed_directory_profiles,
)
