"""Point-in-time age profile for approved and still-open requisitions.

A requisition counts once (not per position or application). Remaining WTE
comes from the canonical vacancy snapshot, which applies actual starter events.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

from workforce_intelligence.recruitment import OPEN_STATUSES, vacancy_snapshots


@dataclass(frozen=True)
class AgeingBand:
    code: str
    label: str
    requisitions: int
    open_wte: float


@dataclass(frozen=True)
class AgedVacancy:
    id: str
    title: str
    status: str
    approved_on: str
    age_days: int
    open_wte: float


@dataclass(frozen=True)
class VacancyAgeing:
    as_of_date: str
    bands: list[AgeingBand]
    total_open_requisitions: int
    total_open_wte: float
    oldest_open: list[AgedVacancy]


# Inclusive limits, following the product specification §9.5.
AGE_BANDS = (
    ("0_30", "0–30 days", 0, 30),
    ("31_60", "31–60 days", 31, 60),
    ("61_90", "61–90 days", 61, 90),
    ("91_180", "91–180 days", 91, 180),
    ("181_plus", "Over 180 days", 181, None),
)


def vacancy_ageing(connection: sqlite3.Connection, as_of: date) -> VacancyAgeing:
    """Read all effective vacancies; never use the paginated UI vacancy list."""
    cutoff = as_of.isoformat()
    open_vacancies = [
        item for item in vacancy_snapshots(connection, cutoff) if item.status in OPEN_STATUSES
    ]
    aged = [
        AgedVacancy(
            id=item.id,
            title=item.title,
            status=item.status,
            approved_on=item.approved_on,
            age_days=(as_of - date.fromisoformat(item.approved_on)).days,
            open_wte=item.open_wte,
        )
        for item in open_vacancies
    ]
    bands = []
    for code, label, minimum, maximum in AGE_BANDS:
        subset = [
            item
            for item in aged
            if minimum <= item.age_days and (maximum is None or item.age_days <= maximum)
        ]
        bands.append(
            AgeingBand(
                code=code,
                label=label,
                requisitions=len(subset),
                open_wte=round(sum(item.open_wte for item in subset), 3),
            )
        )
    aged.sort(key=lambda item: (-item.age_days, item.id))
    return VacancyAgeing(
        as_of_date=cutoff,
        bands=bands,
        total_open_requisitions=len(aged),
        total_open_wte=round(sum(item.open_wte for item in aged), 3),
        oldest_open=aged[:12],
    )
