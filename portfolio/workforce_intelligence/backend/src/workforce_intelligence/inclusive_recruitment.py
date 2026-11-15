"""Aggregate-only inclusive recruitment with conservative disclosure controls.

No HTTP filters, group IDs, candidate IDs, individual attributes, or raw cells
are exported. Any sensitive 1–4 cell or complementary interval suppresses its
entire demographic dimension before serialisation, to prevent subtraction.
"""

import sqlite3
from dataclasses import dataclass
from typing import Literal

MIN_GROUP_SIZE = 5

CATEGORIES = {
    "age_band": ("18-24", "25-34", "35-44", "45-54", "55-64", "65-plus", "not-stated"),
    "ethnicity_group": ("white", "mixed", "asian", "black", "other", "not-stated"),
    "disability_status": ("no", "yes", "not-stated"),
}
COUNTS = (
    "applications",
    "screened",
    "shortlisted",
    "interviewed",
    "offers_made",
    "accepted_offers",
    "starters",
)


@dataclass(frozen=True)
class InclusiveRecruitmentGroup:
    code: str
    applications: int | None
    screened: int | None
    shortlisted: int | None
    interviewed: int | None
    offers_made: int | None
    accepted_offers: int | None
    starters: int | None
    representation_percent: float | None
    shortlisting_percent: float | None
    interview_percent: float | None
    offer_acceptance_percent: float | None
    appointment_percent: float | None


@dataclass(frozen=True)
class InclusiveRecruitmentDimension:
    code: str
    status: Literal["available", "suppressed", "unavailable"]
    message: str | None
    groups: list[InclusiveRecruitmentGroup]


@dataclass(frozen=True)
class InclusiveRecruitmentReport:
    as_of_date: str
    threshold: int
    scope: Literal["all_observed_applications"]
    dimensions: list[InclusiveRecruitmentDimension]


# Only aggregated metrics enter the return value. Application IDs stay inside SQL
# EXISTS, avoiding duplicate events/offers inflating application-grain counts.
_COHORT_SQL = """
WITH stages AS (
    SELECT application_id,
           MAX(CASE WHEN stage_code = 'screened' THEN 1 ELSE 0 END) AS screened,
           MAX(CASE WHEN stage_code = 'shortlisted' THEN 1 ELSE 0 END) AS shortlisted,
           MAX(CASE WHEN stage_code = 'interviewed' THEN 1 ELSE 0 END) AS interviewed
    FROM fact_application_stage_event
    WHERE occurred_on <= :cutoff
    GROUP BY application_id
), offered AS (
    SELECT application_id,
           1 AS offers_made,
           MAX(CASE WHEN outcome = 'accepted' AND resolved_on <= :cutoff
                    THEN 1 ELSE 0 END) AS accepted_offers
    FROM fact_offer
    WHERE offered_on <= :cutoff
    GROUP BY application_id
), started AS (
    SELECT application_id, 1 AS starters
    FROM fact_new_starter
    WHERE started_on <= :cutoff
    GROUP BY application_id
)
SELECT demographic.age_band, demographic.ethnicity_group, demographic.disability_status,
       COALESCE(stages.screened, 0) AS screened,
       COALESCE(stages.shortlisted, 0) AS shortlisted,
       COALESCE(stages.interviewed, 0) AS interviewed,
       COALESCE(offered.offers_made, 0) AS offers_made,
       COALESCE(offered.accepted_offers, 0) AS accepted_offers,
       COALESCE(started.starters, 0) AS starters
FROM fact_application app
LEFT JOIN candidate_demographics demographic ON demographic.application_id = app.id
LEFT JOIN stages ON stages.application_id = app.id
LEFT JOIN offered ON offered.application_id = app.id
LEFT JOIN started ON started.application_id = app.id
WHERE app.received_on <= :cutoff
"""


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def _suppression_required(counters: dict[str, dict[str, int]]) -> bool:
    """Hide the whole dimension if a cell or any reconstructable difference is 1–4.

    Checking all pairwise stage differences also protects complementary cells,
    such as applicants minus shortlisted and offers made minus accepted offers.
    """
    for counts in counters.values():
        values = [counts[name] for name in COUNTS]
        if any(0 < value < MIN_GROUP_SIZE for value in values):
            return True
        if any(
            0 < abs(left - right) < MIN_GROUP_SIZE
            for index, left in enumerate(values)
            for right in values[index + 1 :]
        ):
            return True
    return False


def inclusive_recruitment(
    connection: sqlite3.Connection, *, as_of_date: str
) -> InclusiveRecruitmentReport:
    counters = {
        dimension: {code: dict.fromkeys(COUNTS, 0) for code in categories}
        for dimension, categories in CATEGORIES.items()
    }
    cohort_size = 0
    for record in connection.execute(_COHORT_SQL, {"cutoff": as_of_date}):
        cohort_size += 1
        for dimension, categories in CATEGORIES.items():
            observed = record[dimension]
            code = observed if observed in categories else "not-stated"
            bucket = counters[dimension][code]
            bucket["applications"] += 1
            for name in COUNTS[1:]:
                bucket[name] += int(record[name])

    dimensions = []
    for dimension, groups in counters.items():
        suppressed = _suppression_required(groups) if cohort_size else False
        status: Literal["available", "suppressed", "unavailable"] = (
            "unavailable" if not cohort_size else "suppressed" if suppressed else "available"
        )
        message = (
            "No eligible applications in the observed dataset."
            if not cohort_size
            else "Suppressed: one or more cells or complementary differences are below 5."
            if suppressed
            else None
        )
        published = []
        for code, counts in groups.items():
            show = status == "available"
            applications = counts["applications"]
            published.append(
                InclusiveRecruitmentGroup(
                    code=code,
                    **{name: counts[name] if show else None for name in COUNTS},
                    representation_percent=_percent(applications, cohort_size) if show else None,
                    shortlisting_percent=(
                        _percent(counts["shortlisted"], applications) if show else None
                    ),
                    interview_percent=(
                        _percent(counts["interviewed"], applications) if show else None
                    ),
                    offer_acceptance_percent=(
                        _percent(counts["accepted_offers"], counts["offers_made"]) if show else None
                    ),
                    appointment_percent=(
                        _percent(counts["starters"], applications) if show else None
                    ),
                )
            )
        dimensions.append(InclusiveRecruitmentDimension(dimension, status, message, published))
    return InclusiveRecruitmentReport(
        as_of_date, MIN_GROUP_SIZE, "all_observed_applications", dimensions
    )
