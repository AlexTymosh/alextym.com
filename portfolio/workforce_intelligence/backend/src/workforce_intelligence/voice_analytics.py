"""Representation, confidentiality, and review priority for a generated survey."""

import json
from collections import Counter, defaultdict
from typing import NamedTuple

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import InvalidOperation, current_dataset
from workforce_intelligence.schemas import DatasetResponse
from workforce_intelligence.voice_campaigns import campaign
from workforce_intelligence.voice_taxonomy import (
    DIMENSIONS,
    SERIOUS_THEMES,
    THEMES,
    WEIGHT_DIMENSIONS,
)

WEIGHT_VERSION = "post-stratified-1"
PRIORITY_VERSION = "review-priority-1"
COMPONENT_WEIGHTS = {
    "prevalence": 0.30,
    "severity": 0.30,
    "strategic_relevance": 0.20,
    "segment_concentration": 0.10,
    "trend_change": 0.10,
}
SEVERITY = {"Low": 25, "Medium": 50, "High": 75, "Critical": 100}


class Response(NamedTuple):
    identity: str
    analysable: bool
    groups: dict[str, str]


class VoiceAnalyticsResponse(DatasetResponse):
    report: dict


def ratio(numerator: float, denominator: float) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def protected(total: int, matched: int, minimum: int) -> bool:
    """Suppress a small denominator, a small nonzero cell, or its complement."""
    return total < minimum or 0 < matched < minimum or 0 < total - matched < minimum


def effective_sample_size(weights: list[float]) -> float | None:
    return round(sum(weights) ** 2 / sum(weight**2 for weight in weights), 2) if weights else None


def representation_weights(
    eligible: dict[str, int],
    responded: dict[str, int],
    low: float,
    high: float,
    minimum: int,
) -> dict[str, float] | None:
    if (
        not eligible
        or set(eligible) != set(responded)
        or any(
            protected(eligible[category], responded[category], minimum)
            or responded[category] < minimum
            for category in eligible
        )
    ):
        return None
    population_total, response_total = sum(eligible.values()), sum(responded.values())
    return {
        category: min(
            high, max(low, (count / population_total) / (responded[category] / response_total))
        )
        for category, count in eligible.items()
    }


def priority(
    theme: str,
    severity: str,
    prevalence: float | None,
    concentration: float | None = None,
    trend: float | None = None,
    serious: bool = False,
) -> dict:
    components = {
        "prevalence": prevalence or 0,
        "severity": SEVERITY[severity],
        "strategic_relevance": 100
        if theme in SERIOUS_THEMES
        else 75
        if theme
        in {
            "workload",
            "wellbeing",
            "development",
            "onboarding",
            "psychological-safety",
            "progression",
        }
        else 50,
        "segment_concentration": round(min(100, max(0, (concentration or 0) * 2)), 2),
        "trend_change": round(min(100, max(0, (trend or 0) * 2)), 2),
    }
    return {
        "version": PRIORITY_VERSION,
        "score": round(sum(value * COMPONENT_WEIGHTS[key] for key, value in components.items()), 2),
        "components": components,
        "weights": COMPONENT_WEIGHTS,
        "priority_human_review": serious
        or theme in {"safety", "speaking-up"}
        or severity == "Critical",
        "trend_available": trend is not None,
        "segment_available": concentration is not None,
    }


def _panel(connection, survey_id: str):
    rows = connection.execute(
        """
        SELECT r.id, r.comment IS NOT NULL AS analysable, context.segments FROM survey_responses r
        JOIN voice_response_context context ON context.response_id = r.id WHERE r.survey_id = ? ORDER BY r.id
        """,
        (survey_id,),
    )
    respondents = [
        Response(row["id"], bool(row["analysable"]), json.loads(row["segments"])) for row in rows
    ]
    mentions: dict[str, set[str]] = defaultdict(set)
    frequency: Counter[str] = Counter()
    severity: dict[str, str] = {}
    for row in connection.execute(
        """
        SELECT theme, severity, response_id FROM survey_response_themes AS mention JOIN survey_responses r
        ON r.id = mention.response_id WHERE r.survey_id = ?
        """,
        (survey_id,),
    ):
        mentions[row["theme"]].add(row["response_id"])
        frequency[row["theme"]] += 1
        if SEVERITY[row["severity"]] > SEVERITY.get(severity.get(row["theme"], ""), 0):
            severity[row["theme"]] = row["severity"]
    return respondents, mentions, frequency, severity


def _basis(connection, survey_id: str, dimension: str) -> dict[str, tuple[int, int]]:
    return {
        row["category"]: (row["eligible"], row["invited"])
        for row in connection.execute(
            """SELECT category, eligible, invited FROM voice_population
        WHERE survey_id = ? AND dimension = ? ORDER BY category""",
            (survey_id, dimension),
        )
    }


def _cohort_report(analysable, hits: set[str], weights, weight_by: str, minimum: int) -> dict:
    total = len(analysable)
    mentioned = sum(item.identity in hits for item in analysable)
    if protected(total, mentioned, minimum):
        return {
            "status": "suppressed",
            "responses": None,
            "analysable": None,
            "unweighted": None,
            "weighted": None,
            "effective_sample": None,
        }
    sample = [weights[item.groups[weight_by]] for item in analysable] if weights else []
    return {
        "status": "available",
        "responses": mentioned,
        "analysable": total,
        "unweighted": ratio(mentioned, total),
        "weighted": ratio(
            sum(
                weight
                for item, weight in zip(analysable, sample, strict=False)
                if item.identity in hits
            ),
            sum(sample),
        )
        if sample
        else None,
        "effective_sample": effective_sample_size(sample),
    }


def _partition(connection, info, dimension, respondents, hits, weights, weight_by, previous):
    # Suppress the whole partition rather than leaving a single suppressed row
    # reconstructable from the overall figure and the other rows.
    minimum = info["anonymity_min"]
    groups: dict[str, list[Response]] = defaultdict(list)
    for item in respondents:
        groups[item.groups[dimension]].append(item)
    population = _basis(connection, info["survey_id"], dimension)
    result = []
    for label, (eligible, invited) in population.items():
        group = groups[label]
        analytical = [item for item in group if item.analysable]
        metrics = _cohort_report(analytical, hits, weights, weight_by, minimum)
        if (
            int(invited) < minimum
            or protected(invited, len(group), minimum)
            or protected(len(group), len(analytical), minimum)
            or metrics["status"] != "available"
        ):
            return []
        prior = previous.get(label)
        result.append(
            {
                "category": label,
                "eligible": eligible,
                "invited": invited,
                "responded": len(group),
                "response_rate": ratio(len(group), invited),
                **metrics,
                "trend_pp": round(metrics["unweighted"] - prior, 2)
                if prior is not None and metrics["unweighted"] is not None
                else None,
            }
        )
    return result


def _previous(connection, info):
    return connection.execute(
        """
        SELECT settings.survey_id FROM voice_campaign_settings settings
        JOIN survey_campaigns campaign ON campaign.id = settings.survey_id
        WHERE settings.generated_at IS NOT NULL AND settings.series = :series
          AND settings.audience = :audience AND settings.organisation_id IS :organisation_id
          AND campaign.period_end < :period_start
        ORDER BY campaign.period_end DESC, settings.survey_id LIMIT 1
        """,
        info,
    ).fetchone()


def _triangulate(connection, info):
    values = []
    for dimension, match, label in (
        (
            "learning",
            "Completed learning",
            "Completed learning in the year before the survey cutoff",
        ),
        ("pdr", "completed", "Latest PDR recorded as completed by the survey cutoff"),
    ):
        rows = _basis(connection, info["survey_id"], dimension)
        numerator, denominator = (
            rows.get(match, (0, 0))[0],
            sum(values[0] for values in rows.values()),
        )
        if not protected(denominator, numerator, info["anonymity_min"]):
            values.append(
                {
                    "indicator": label,
                    "eligible": denominator,
                    "count": numerator,
                    "percent": ratio(numerator, denominator),
                    "relation": "Observed alongside; this does not establish causation.",
                }
            )
    return values


def _rating_summary(connection, info):
    return [
        {
            "question": row["prompt"],
            "scale_max": row["scale_max"],
            "mean": round(row["mean"], 2) if row["answered"] >= info["anonymity_min"] else None,
            "answered": row["answered"] if row["answered"] >= info["anonymity_min"] else None,
        }
        for row in connection.execute(
            """
            SELECT question.prompt, question.scale_max, COUNT(rating.rating) AS answered, AVG(rating.rating) AS mean
            FROM survey_questions question
            LEFT JOIN survey_responses response ON response.survey_id = question.survey_id
            LEFT JOIN voice_rating_responses rating ON rating.response_id = response.id AND rating.question_code = question.code
            WHERE question.survey_id = ? AND question.kind = 'rating' GROUP BY question.code ORDER BY question.position
            """,
            (info["survey_id"],),
        )
    ]


def analyse_survey(
    database: Database,
    survey_id: str,
    dimension: str,
    weight_by: str,
    theme: str,
    trim_min: float,
    trim_max: float,
) -> VoiceAnalyticsResponse:
    if dimension not in DIMENSIONS or weight_by not in WEIGHT_DIMENSIONS or theme not in THEMES:
        raise InvalidOperation("Choose one approved grouping, representation method and theme.")
    if not 0.25 <= trim_min <= 1 <= trim_max <= 4:
        raise InvalidOperation("Choose a trimming range containing 1.0.")
    with database.transaction() as conn:
        state = current_dataset(conn)
        info = campaign(conn, survey_id)
        respondents, mentions, frequency, severities = _panel(conn, survey_id)
        minimum = info["anonymity_min"]
        population = _basis(conn, survey_id, weight_by)
        weights = representation_weights(
            {category: values[0] for category, values in population.items()},
            Counter(response.groups[weight_by] for response in respondents),
            trim_min,
            trim_max,
            minimum,
        )
        all_text = [response for response in respondents if response.analysable]
        previous = _previous(conn, info)
        prior_pct = None
        prior_groups = {}
        if previous:
            prior = campaign(conn, previous[0])
            prior_responses, prior_mentions, _, _ = _panel(conn, previous[0])
            old = _cohort_report(
                [r for r in prior_responses if r.analysable],
                prior_mentions[theme],
                None,
                weight_by,
                max(minimum, prior["anonymity_min"]),
            )
            prior_pct = old["unweighted"]
            prior_groups = {
                row["category"]: row["unweighted"]
                for row in _partition(
                    conn,
                    prior,
                    dimension,
                    prior_responses,
                    prior_mentions[theme],
                    None,
                    weight_by,
                    {},
                )
            }
        headline = _cohort_report(all_text, mentions[theme], weights, weight_by, minimum)
        overall = headline["unweighted"]
        segments = _partition(
            conn, info, dimension, respondents, mentions[theme], weights, weight_by, prior_groups
        )
        for row in segments:
            row["difference_pp"] = (
                round(row["unweighted"] - overall, 2) if overall is not None else None
            )
            row["prevalence_ratio"] = round(row["unweighted"] / overall, 2) if overall else None
        trend = (
            round(overall - prior_pct, 2) if overall is not None and prior_pct is not None else None
        )
        all_themes = []
        for key, label in THEMES.items():
            if key not in mentions:
                continue
            row = _cohort_report(all_text, mentions[key], weights, weight_by, minimum)
            if row["status"] == "available":
                all_themes.append({"theme": key, "label": label, **row, "mentions": frequency[key]})
        report = {
            "survey_id": survey_id,
            "dimension": dimension,
            "theme": theme,
            **headline,
            "minimum": minimum,
            "weighting": {
                "status": "Weighted" if weights else "Weighting not available",
                "version": WEIGHT_VERSION,
                "dimension": weight_by,
                "trim_min": trim_min,
                "trim_max": trim_max,
                "source": "Eligible population snapshot at response generation",
                "population_revision": info["population_revision"],
                "groups": [
                    {
                        "category": group,
                        "eligible": population[group][0],
                        "weight": round(weight, 4),
                    }
                    for group, weight in weights.items()
                ]
                if weights
                else [],
            },
            "theme_frequencies": all_themes,
            "segments": segments,
            "segments_suppressed": bool(respondents and not segments),
            "trend_pp": trend,
            "comparison_survey_id": previous[0] if trend is not None and previous else None,
            "nonresponse_rate": ratio(info["invited"] - len(respondents), info["invited"])
            if respondents
            else None,
            "item_nonresponse_rate": ratio(len(respondents) - len(all_text), len(respondents)),
            "ratings": _rating_summary(conn, info),
            "triangulation": _triangulate(conn, info),
            "priority": priority(
                theme,
                severities.get(theme, "Low"),
                overall,
                max(
                    (row["difference_pp"] for row in segments if row["difference_pp"] is not None),
                    default=None,
                ),
                trend,
            )
            if theme in severities and headline["status"] == "available"
            else None,
            "requires_human_attention": any(
                code in SERIOUS_THEMES or level == "Critical" for code, level in severities.items()
            ),
        }
        return VoiceAnalyticsResponse(dataset=state, report=report)
