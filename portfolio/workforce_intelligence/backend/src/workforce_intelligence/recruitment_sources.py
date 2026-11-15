"""Source-cohort recruitment analytics (no demographic breakdowns).

The cohort is one distinct application received in the requested period.
Subsequent events are observed through the reporting cutoff, including after
receipt period start; counting never joins event-grain records together.
"""

import sqlite3
from dataclasses import dataclass

from workforce_intelligence.analytics import ReportingWindow


@dataclass(frozen=True)
class RecruitmentSourceRow:
    source_code: str
    applications: int
    screened: int
    shortlisted: int
    interviewed: int
    accepted_offers: int
    starters: int
    application_to_start_percent: float | None


@dataclass(frozen=True)
class RecruitmentSourceReport:
    window: ReportingWindow
    campaign_id: str | None
    organisation_id: str | None
    location_id: str | None
    role_id: str | None
    rows: list[RecruitmentSourceRow]
    total_applications: int


_SOURCE_COHORT_SQL = """
WITH cohort AS (
    SELECT app.id, app.source_code, app.vacancy_id
    FROM fact_application app
    WHERE app.received_on BETWEEN :start AND :cutoff
      AND (:campaign_id IS NULL OR app.campaign_id = :campaign_id)
      AND (:organisation_id IS NULL OR app.organisation_id = :organisation_id)
      AND (:location_id IS NULL OR app.location_id = :location_id)
      AND (:role_id IS NULL OR app.role_id = :role_id)
), observed AS (
    SELECT app.source_code,
           EXISTS (
               SELECT 1 FROM fact_application_stage_event event
               WHERE event.application_id = app.id AND event.stage_code = 'screened'
                 AND event.occurred_on <= :cutoff
           ) AS screened,
           EXISTS (
               SELECT 1 FROM fact_application_stage_event event
               WHERE event.application_id = app.id AND event.stage_code = 'shortlisted'
                 AND event.occurred_on <= :cutoff
           ) AS shortlisted,
           EXISTS (
               SELECT 1 FROM fact_application_stage_event event
               WHERE event.application_id = app.id AND event.stage_code = 'interviewed'
                 AND event.occurred_on <= :cutoff
           ) AS interviewed,
           EXISTS (
               SELECT 1 FROM fact_offer offer
               WHERE offer.application_id = app.id AND offer.outcome = 'accepted'
                 AND offer.resolved_on <= :cutoff
           ) AS accepted,
           EXISTS (
               SELECT 1 FROM fact_new_starter starter
               WHERE starter.application_id = app.id AND starter.started_on <= :cutoff
           ) AS started
    FROM cohort app
)
SELECT source_code, COUNT(*) AS applications, SUM(screened) AS screened,
       SUM(shortlisted) AS shortlisted, SUM(interviewed) AS interviewed,
       SUM(accepted) AS accepted_offers, SUM(started) AS starters
FROM observed
GROUP BY source_code
ORDER BY applications DESC, source_code ASC
"""


def recruitment_sources(
    connection: sqlite3.Connection,
    window: ReportingWindow,
    *,
    campaign_id: str | None = None,
    organisation_id: str | None = None,
    location_id: str | None = None,
    role_id: str | None = None,
) -> RecruitmentSourceReport:
    params = {
        "start": window.start.isoformat(),
        "cutoff": window.end.isoformat(),
        "campaign_id": campaign_id,
        "organisation_id": organisation_id,
        "location_id": location_id,
        "role_id": role_id,
    }
    rows = []
    for item in connection.execute(_SOURCE_COHORT_SQL, params):
        applications = item["applications"]
        starters = item["starters"]
        rows.append(
            RecruitmentSourceRow(
                source_code=item["source_code"],
                applications=applications,
                screened=item["screened"],
                shortlisted=item["shortlisted"],
                interviewed=item["interviewed"],
                accepted_offers=item["accepted_offers"],
                starters=starters,
                application_to_start_percent=round(starters * 100 / applications, 2),
            )
        )
    return RecruitmentSourceReport(
        window=window,
        campaign_id=campaign_id,
        organisation_id=organisation_id,
        location_id=location_id,
        role_id=role_id,
        rows=rows,
        total_applications=sum(item.applications for item in rows),
    )
