"""Evidence and Gold read model for the controlled People Voice report."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    response_id: str
    comment: str


@dataclass(frozen=True)
class ReviewedFinding:
    id: str
    theme: str
    classification: str
    severity: str
    summary: str
    evidence: list[Evidence]
    prevalence: float | None
    review_kind: str
    review_rationale: str
    reviewed_on: str
    published_on: str


@dataclass(frozen=True)
class DraftFinding:
    id: str
    theme: str
    review_status: str


@dataclass(frozen=True)
class ManagementAction:
    id: str
    signal_id: str
    title: str
    assigned_team: str
    status: str
    due_on: str


@dataclass(frozen=True)
class SurveyReport:
    survey_id: str
    title: str
    question: str
    period_start: str
    period_end: str
    invited: int
    total_responses: int
    analysable_responses: int
    response_rate: float
    analysis_id: str
    analysed_on: str
    analysis_label: str
    findings: list[ReviewedFinding]
    drafts: list[DraftFinding]
    actions: list[ManagementAction]


def link_evidence(
    connection: sqlite3.Connection, signal_id: str, response_ids: tuple[str, ...]
) -> None:
    """Require a known signal and distinct analysed comments from its own survey."""
    if not response_ids or len(set(response_ids)) != len(response_ids):
        raise ValueError("Evidence must contain distinct response IDs")
    scope = connection.execute(
        """
        SELECT analysis.survey_id FROM ai_signals AS signal
        JOIN ai_analyses AS analysis ON analysis.id = signal.analysis_id WHERE signal.id = ?
        """,
        (signal_id,),
    ).fetchone()
    if scope is None:
        raise ValueError("Unknown signal")
    known = {
        row[0]
        for row in connection.execute(
            "SELECT id FROM survey_responses WHERE survey_id = ? AND comment IS NOT NULL",
            (scope[0],),
        )
    }
    if not set(response_ids).issubset(known):
        raise ValueError("Unknown or ineligible evidence response ID")
    connection.executemany(
        "INSERT INTO survey_signal_evidence (signal_id, response_id) VALUES (?, ?)",
        [(signal_id, response_id) for response_id in response_ids],
    )


def read_survey_report(connection: sqlite3.Connection, analysis_id: str) -> SurveyReport | None:
    details = connection.execute(
        """
        SELECT campaign.id AS survey_id, campaign.title, campaign.question, campaign.period_start,
               campaign.period_end, campaign.invited, analysis.id AS analysis_id, analysis.analysed_on,
               analysis.analysis_label, COUNT(response.id) AS total_responses,
               COUNT(response.comment) AS analysable_responses
        FROM ai_analyses AS analysis JOIN survey_campaigns AS campaign ON campaign.id = analysis.survey_id
        LEFT JOIN survey_responses AS response ON response.survey_id = campaign.id
        WHERE analysis.id = ? GROUP BY analysis.id, campaign.id
        """,
        (analysis_id,),
    ).fetchone()
    if details is None:
        return None
    published = connection.execute(
        """
        SELECT id, theme, classification, severity, summary, review_kind, review_rationale,
               reviewed_on, published_on
        FROM gold_reviewed_survey_findings WHERE analysis_id = ? ORDER BY id
        """,
        (analysis_id,),
    ).fetchall()
    findings = []
    for finding in published:
        evidence = [
            Evidence(response_id=row["id"], comment=row["comment"])
            for row in connection.execute(
                """
                SELECT response.id, response.comment FROM survey_signal_evidence AS evidence
                JOIN survey_responses AS response ON response.id = evidence.response_id
                WHERE evidence.signal_id = ? ORDER BY response.id
                """,
                (finding["id"],),
            )
        ]
        findings.append(
            ReviewedFinding(
                **dict(finding),
                evidence=evidence,
                prevalence=round(100 * len(evidence) / details["analysable_responses"], 2)
                if details["analysable_responses"]
                else None,
            )
        )

    drafts = [
        DraftFinding(row["id"], row["theme"], "Awaiting analyst review")
        for row in connection.execute(
            """
        SELECT signal.id, signal.theme FROM ai_signals AS signal
        LEFT JOIN analyst_reviews AS review ON review.signal_id = signal.id
        WHERE signal.analysis_id = ? AND review.id IS NULL ORDER BY signal.id
        """,
            (analysis_id,),
        )
    ]
    actions = [
        ManagementAction(**dict(row))
        for row in connection.execute(
            """
        SELECT action.id, action.signal_id, action.title, action.assigned_team, action.status, action.due_on
        FROM management_actions AS action JOIN gold_reviewed_survey_findings AS finding
          ON finding.id = action.signal_id WHERE finding.analysis_id = ? ORDER BY action.id
        """,
            (analysis_id,),
        )
    ]
    return SurveyReport(
        **dict(details),
        response_rate=round(100 * details["total_responses"] / details["invited"], 2),
        findings=findings,
        drafts=drafts,
        actions=actions,
    )
