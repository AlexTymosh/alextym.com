"""Create a survey and a reproducible, synthetic cross-section of responses."""

import json
import re
from collections import Counter
from datetime import date, timedelta
from hashlib import sha256
from random import Random
from secrets import randbits
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    InvalidOperation,
    RecordNotFound,
    current_dataset,
)
from workforce_intelligence.operation_store import SourceEditor
from workforce_intelligence.schemas import DatasetRequest, DatasetResponse, EntityId
from workforce_intelligence.voice_taxonomy import (
    CANDIDATE_RATINGS,
    DIMENSIONS,
    QUESTION_BANK,
    SERIES,
    TAXONOMY_VERSION,
    THEMES,
    WEIGHT_DIMENSIONS,
    generated_feedback,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=160)]
Percent = Annotated[int, Field(strict=True, ge=0, le=100)]
Seed = Annotated[int, Field(strict=True, ge=0, le=2**32 - 1)]
Audience = Literal["employees", "new_starters", "exit", "candidates"]
Series = Literal["general", "onboarding", "development", "candidate"]
TEMPLATE_ID = "candidate-feedback"


class SurveyQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: EntityId
    prompt: Text
    kind: Literal["comment", "rating"]
    scale_max: Literal[5, 7] | None = None

    @model_validator(mode="after")
    def check_scale(self):
        if (self.kind == "rating") != (self.scale_max is not None):
            raise ValueError("Provide a scale for rating questions only.")
        return self


class CampaignCreate(DatasetRequest):
    survey_id: EntityId
    title: Text
    audience: Audience = "employees"
    organisation_id: EntityId | None = None
    series: Series = "general"
    period_start: date
    period_end: date
    anonymity_min: Annotated[int, Field(strict=True, ge=5, le=30)] = 5
    invited: Annotated[int, Field(strict=True, ge=5, le=5000)] | None = None
    questions: Annotated[list[SurveyQuestion], Field(min_length=1, max_length=5)]

    @model_validator(mode="after")
    def check_questions(self):
        if (self.series == "candidate") != (self.audience == "candidates"):
            raise ValueError("Use the candidate template with the candidate audience.")
        if self.period_end < self.period_start:
            raise ValueError("Survey end date cannot precede its start.")
        if len({question.code for question in self.questions}) != len(self.questions):
            raise ValueError("Question codes must be unique in the campaign.")
        if sum(question.kind == "comment" for question in self.questions) != 1:
            raise ValueError("Include one free-text question and up to four rating questions.")
        return self


class GenerateResponses(DatasetRequest):
    mode: Literal["balanced", "emerging", "significant", "exploratory"]
    seed: Seed | None = None
    count: Annotated[int, Field(strict=True, ge=5, le=240)]
    analysable_percent: Percent = 90
    positive_percent: Percent = 25
    negative_percent: Percent = 55
    theme_percent: Percent = 65
    ambiguous_percent: Percent = 8
    severity: Literal["Low", "Medium", "High", "Critical"] | None = None

    @model_validator(mode="after")
    def check_mix(self):
        if self.positive_percent + self.negative_percent > 100:
            raise ValueError("Positive and negative shares must total at most 100%.")
        return self


class VoiceWorkspace(DatasetResponse):
    campaigns: list[dict]
    units: list[dict]
    bank: list[dict]
    dimensions: dict[str, str]
    weighting_dimensions: list[str]
    themes: dict[str, str]
    series: dict[str, str]


class CampaignResponse(DatasetResponse):
    campaign: dict


def _eligible(connection, *, audience: str, organisation_id: str | None, start: str, end: str):
    rows = connection.execute(
        """
        WITH cohort AS (
            SELECT e.id, CASE WHEN :audience = 'exit' THEN date(leaver.leaving_date, '-1 day')
                              ELSE :end END AS cutoff,
                   (SELECT MIN(valid_from) FROM employment_contracts WHERE employee_id = e.id) AS hired_on
            FROM employees e LEFT JOIN leaver_events leaver ON leaver.employee_id = e.id
            WHERE :audience != 'exit' OR leaver.leaving_date BETWEEN :start AND :end
        )
        SELECT cohort.*, unit.id AS unit_code, unit.label AS organisation,
               loc.label AS location, role.id AS role_code, role.label AS role, role.pay_band,
               c.contracted_fte_milli AS fte, c.is_substantive, a.valid_from AS role_since,
               COALESCE(p.age_band, 'not-stated') AS age,
               COALESCE(p.ethnicity_group, 'not-stated') AS ethnicity,
               COALESCE(p.disability_status, 'not-stated') AS disability,
               COALESCE(app.source_code, 'Not recorded') AS recruitment_source,
               COALESCE((SELECT pdr.status FROM pdr_events pdr WHERE pdr.employee_id = cohort.id
                  AND pdr.occurred_on <= cohort.cutoff ORDER BY pdr.occurred_on DESC LIMIT 1), 'Not recorded') AS pdr,
               EXISTS (SELECT 1 FROM learning_events item WHERE item.employee_id = cohort.id AND item.completed = 1
                       AND item.occurred_on BETWEEN date(cohort.cutoff, '-365 days') AND cohort.cutoff) AS learned,
               EXISTS (SELECT 1 FROM promotion_events item WHERE item.employee_id = cohort.id
                       AND item.kind = 'promotion' AND item.occurred_on BETWEEN date(cohort.cutoff, '-365 days') AND cohort.cutoff) AS promoted
        FROM cohort
        JOIN employment_contracts c ON c.employee_id = cohort.id
          AND c.valid_from <= cohort.cutoff AND (c.valid_to IS NULL OR c.valid_to > cohort.cutoff)
        JOIN organisation_assignments a ON a.employee_id = cohort.id
          AND a.valid_from <= cohort.cutoff AND (a.valid_to IS NULL OR a.valid_to > cohort.cutoff)
        JOIN establishment_lines line ON line.id = a.line_id
        JOIN organisational_units unit ON unit.id = line.organisation_id
        JOIN locations loc ON loc.id = line.location_id
        JOIN roles role ON role.id = line.role_id
        LEFT JOIN employee_profiles p ON p.employee_id = cohort.id
        LEFT JOIN starter_events s ON s.employee_id = cohort.id
        LEFT JOIN offers o ON o.id = s.offer_id
        LEFT JOIN candidate_applications app ON app.id = o.application_id
        WHERE (:organisation IS NULL OR unit.id = :organisation)
          AND (:audience != 'new_starters' OR cohort.hired_on >= date(cohort.cutoff, '-365 days'))
        ORDER BY cohort.id
        """,
        {"audience": audience, "organisation": organisation_id, "start": start, "end": end},
    ).fetchall()
    return rows


def _segments(row, audience: str) -> dict[str, str]:
    cutoff = date.fromisoformat(row["cutoff"])
    tenure = (cutoff - date.fromisoformat(row["hired_on"])).days
    months = (cutoff - date.fromisoformat(row["role_since"])).days // 30
    code = row["role_code"]
    clinical = code in {"clinician", "crew", "role-01", "role-03", "role-06", "role-07", "role-18"}
    grouping = "Clinical" if clinical else "Non-clinical"
    location = row["location"]
    proxy = re.fullmatch(r"Demo ([NWES])\d+ Base", location)
    if proxy:
        location = {"N": "North", "W": "West", "E": "East", "S": "South"}[proxy[1]]
    # This proxy has no influence on sampling, weight or priority.
    qualification = int.from_bytes(sha256(row["id"].encode()).digest()[:2], "big") % 10
    return {
        "service": "Clinical operations" if clinical else "Support and control",
        "organisation": row["organisation"],
        "location": location,
        "role": row["role"],
        "pay_band": row["pay_band"],
        "clinical": grouping,
        "employment_type": "Substantive" if row["is_substantive"] else "Temporary",
        "fte": "Full time"
        if row["fte"] == 1000
        else "Part time ≥ 0.6"
        if row["fte"] >= 600
        else "Part time < 0.6",
        "tenure": "Under one year"
        if tenure < 365
        else "1–4 years"
        if tenure < 1826
        else "5 or more years",
        "role_months": "0–5 months"
        if months < 6
        else "6–11 months"
        if months < 12
        else "12 or more months",
        "promoted": "Yes" if row["promoted"] else "No",
        "qualified": "Yes" if qualification < 2 else "No",
        "qualification": grouping + " training" if qualification < 5 else "Other or not recorded",
        "starter": "Under three months"
        if tenure < 91
        else "3–12 months"
        if tenure <= 365
        else "Established",
        "leaver": "Exit cohort" if audience == "exit" else "Not an exit survey",
        "source": row["recruitment_source"],
        "pdr": row["pdr"],
        "learning": "Completed learning" if row["learned"] else "None recorded",
        "age": row["age"],
        "ethnicity": row["ethnicity"],
        "disability": row["disability"],
    }


def _candidate_samples(connection, *, organisation_id: str | None, start: str, end: str):
    rows = connection.execute(
        """
        SELECT app.id, unit.label AS organisation, loc.label AS location, role.label AS role,
               role.pay_band, app.source_code AS source,
               EXISTS (SELECT 1 FROM application_stage_events e
                   WHERE e.application_id = app.id AND e.stage_code = 'interviewed'
                     AND e.occurred_on <= :end) AS interviewed
        FROM fact_application app
        JOIN organisational_units unit ON unit.id = app.organisation_id
        JOIN locations loc ON loc.id = app.location_id
        JOIN roles role ON role.id = app.role_id
        WHERE app.received_on BETWEEN :start AND :end
          AND (:organisation IS NULL OR app.organisation_id = :organisation)
        ORDER BY app.id
        """,
        {"start": start, "end": end, "organisation": organisation_id},
    )
    return [
        (
            item["id"],
            {
                **dict.fromkeys(DIMENSIONS, "Not applicable"),
                **{
                    key: item[key]
                    for key in ("organisation", "location", "role", "pay_band", "source")
                },
            },
            bool(item["interviewed"]),
        )
        for item in rows
    ]


def _samples(connection, *, audience: str, organisation_id: str | None, start: str, end: str):
    if audience == "candidates":
        return _candidate_samples(connection, organisation_id=organisation_id, start=start, end=end)
    return [
        (row["id"], _segments(row, audience), True)
        for row in _eligible(
            connection, audience=audience, organisation_id=organisation_id, start=start, end=end
        )
    ]


def campaign(connection, survey_id: str) -> dict:
    row = connection.execute(
        """
        SELECT s.*, c.title, c.question, c.period_start, c.period_end, c.invited,
               (SELECT COUNT(*) FROM survey_responses r WHERE r.survey_id = s.survey_id) AS responses,
               (SELECT COUNT(r.comment) FROM survey_responses r WHERE r.survey_id = s.survey_id) AS analysable
        FROM voice_campaign_settings s JOIN survey_campaigns c ON c.id = s.survey_id WHERE s.survey_id = ?
        """,
        (survey_id,),
    ).fetchone()
    if row is None:
        raise RecordNotFound("Survey campaign not found.")
    info = dict(row)
    info["audience"] = info.pop("candidate_audience") or info["audience"]
    info["questions"] = [
        dict(question)
        for question in connection.execute(
            "SELECT code, prompt, kind, scale_max FROM survey_questions WHERE survey_id = ? ORDER BY position",
            (survey_id,),
        )
    ]
    info["generation_parameters"] = (
        json.loads(info["generation_parameters"]) if info["generation_parameters"] else None
    )
    return info


def workspace(database: Database) -> VoiceWorkspace:
    with database.transaction() as connection:
        state = current_dataset(connection)
        campaigns = [
            campaign(connection, row[0])
            for row in connection.execute(
                """SELECT settings.survey_id FROM voice_campaign_settings settings JOIN survey_campaigns c
            ON c.id = settings.survey_id ORDER BY c.period_end DESC, settings.survey_id LIMIT 40"""
            )
        ]
        units = [
            dict(row)
            for row in connection.execute(
                "SELECT id, label FROM organisational_units WHERE active = 1 ORDER BY label LIMIT 100"
            )
        ]
    return VoiceWorkspace(
        dataset=state,
        campaigns=campaigns,
        units=units,
        bank=list(QUESTION_BANK),
        dimensions=DIMENSIONS,
        weighting_dimensions=sorted(WEIGHT_DIMENSIONS),
        themes=THEMES,
        series=SERIES,
    )


def create_campaign(
    database: Database, actor: AuditActor, command: CampaignCreate
) -> CampaignResponse:
    with database.transaction(write=True) as connection:
        state = current_dataset(connection, command.expected_version())
        editor = SourceEditor(connection, state, actor)
        start, end = editor.day(command.period_start), editor.day(command.period_end)
        if editor.get("survey_campaigns", "id", command.survey_id):
            raise Conflict("That survey code already exists.")
        if connection.execute("SELECT COUNT(*) FROM voice_campaign_settings").fetchone()[0] >= 40:
            raise InvalidOperation("This demo generation already has 40 survey campaigns.")
        if command.organisation_id:
            editor.reference("organisational_units", command.organisation_id)
        eligible = len(
            _samples(
                connection,
                audience=command.audience,
                organisation_id=command.organisation_id,
                start=start,
                end=end,
            )
        )
        invited = command.invited or eligible
        if not command.anonymity_min <= invited <= eligible:
            raise InvalidOperation(
                "Invite between the anonymity minimum and the number of eligible people for this cohort."
            )
        question = next(item.prompt for item in command.questions if item.kind == "comment")
        editor.insert(
            "survey_campaigns",
            {
                "id": command.survey_id,
                "title": command.title,
                "question": question,
                "period_start": start,
                "period_end": end,
                "invited": invited,
            },
        )
        values = {
            "survey_id": command.survey_id,
            "audience": "employees" if command.audience == "candidates" else command.audience,
            "candidate_audience": "candidates" if command.audience == "candidates" else None,
            "organisation_id": command.organisation_id,
            "series": command.series,
            "anonymity_min": command.anonymity_min,
            "eligible": eligible,
            "taxonomy_version": TAXONOMY_VERSION,
        }
        editor.insert("voice_campaign_settings", values)
        for index, item in enumerate(command.questions):
            editor.insert(
                "survey_questions",
                {"survey_id": command.survey_id, **item.model_dump(), "position": index},
            )
        editor.audit(
            "survey",
            command.survey_id,
            "create_campaign",
            None,
            {
                "audience": command.audience,
                "period_start": start,
                "period_end": end,
                "invited": invited,
                "questions": len(command.questions),
            },
        )
        return CampaignResponse(
            dataset=editor.state, campaign=campaign(connection, command.survey_id)
        )


def _draw(random: Random, data, size: int, mode: str):
    if mode in ("balanced", "exploratory"):
        return random.sample(data, size)
    # Order a reproducible sample without replacement. In a concern scenario,
    # one service is overrepresented to show what weighting can and cannot change.
    return sorted(
        data,
        key=lambda item: random.random() ** (1 / (3 if item[1]["clinical"] == "Clinical" else 1)),
        reverse=True,
    )[:size]


def _make_responses(conn, info: dict, data, options: GenerateResponses, seed: int):
    random = Random(seed)
    invitations = random.sample(data, info["invited"])
    picked = _draw(random, invitations, options.count, options.mode)
    eligible = Counter(
        (dimension, category) for _, groups, _ in data for dimension, category in groups.items()
    )
    invited = Counter(
        (dimension, category)
        for _, groups, _ in invitations
        for dimension, category in groups.items()
    )
    conn.executemany(
        "INSERT INTO voice_population VALUES (?, ?, ?, ?, ?)",
        [
            (info["survey_id"], dimension, category, count, invited[(dimension, category)])
            for (dimension, category), count in sorted(eligible.items())
        ],
    )
    start, end = date.fromisoformat(info["period_start"]), date.fromisoformat(info["period_end"])
    prefix = sha256(info["survey_id"].encode()).hexdigest()[:20]
    for number, (_, groups, interviewed) in enumerate(picked, 1):
        response_id = f"voice-{prefix}-{number:03d}"
        submitted = (start + timedelta(days=random.randint(0, (end - start).days))).isoformat()
        value = random.randrange(100)
        direction = (
            "positive"
            if value < options.positive_percent
            else (
                "negative"
                if value < options.positive_percent + options.negative_percent
                else "neutral"
            )
        )
        comment, mentions = None, []
        if random.randrange(100) < options.analysable_percent:
            mode = (
                random.choice(("balanced", "emerging", "significant"))
                if options.mode == "exploratory"
                else options.mode
            )
            chance = options.theme_percent * (
                1 if groups["clinical"] == "Clinical" or mode == "balanced" else 0.55
            )
            comment, mentions = generated_feedback(
                random,
                info["series"],
                mode,
                direction,
                random.randrange(100) < chance,
                random.randrange(100) < options.ambiguous_percent,
                options.severity,
            )
        conn.execute(
            "INSERT INTO survey_responses VALUES (?, ?, ?, ?)",
            (response_id, info["survey_id"], submitted, comment),
        )
        conn.execute(
            "INSERT INTO voice_response_context VALUES (?, ?)",
            (response_id, json.dumps(groups, sort_keys=True)),
        )
        conn.executemany(
            "INSERT INTO survey_response_themes VALUES (?, ?, ?, ?, ?, ?)",
            [(response_id, order, *mention) for order, mention in enumerate(mentions, 1)],
        )
        for question in info["questions"]:
            if question["kind"] == "rating":
                rating = (
                    None
                    if (question["code"] == "interview-experience" and not interviewed)
                    or random.random() < 0.07
                    else min(
                        question["scale_max"],
                        max(
                            1,
                            random.randrange(1, question["scale_max"] + 1)
                            + (direction == "positive")
                            - (direction == "negative"),
                        ),
                    )
                )
                conn.execute(
                    "INSERT INTO voice_rating_responses VALUES (?, ?, ?)",
                    (response_id, question["code"], rating),
                )


def generate_responses(
    database: Database, actor: AuditActor, survey_id: str, options: GenerateResponses
) -> CampaignResponse:
    with database.transaction(write=True) as connection:
        state = current_dataset(connection, options.expected_version())
        info = campaign(connection, survey_id)
        if info["responses"] or info["generated_at"]:
            raise Conflict(
                "This campaign already contains responses. Create a new campaign for another sample."
            )
        if options.count > info["invited"]:
            raise InvalidOperation("Response count cannot exceed the number invited.")
        rows = _samples(
            connection,
            audience=info["audience"],
            organisation_id=info["organisation_id"],
            start=info["period_start"],
            end=info["period_end"],
        )
        if len(rows) < info["invited"]:
            raise Conflict(
                "The eligible population changed. Create a campaign for the current cohort."
            )
        seed = (
            options.seed
            if options.seed is not None
            else (randbits(32) if options.mode == "exploratory" else 1516)
        )
        editor = SourceEditor(connection, state, actor)
        _make_responses(
            connection,
            info,
            rows,
            options,
            seed,
        )
        values = {
            "eligible": len(rows),
            "generated_at": editor.prepare().refreshed_at,
            "generation_seed": seed,
            "generation_mode": options.mode,
            "population_revision": state.revision,
            "generation_parameters": json.dumps(
                options.model_dump(mode="json", exclude={"dataset_id", "dataset_generation"})
            ),
        }
        editor.update("voice_campaign_settings", "survey_id", survey_id, values)
        editor.audit(
            "survey",
            survey_id,
            "generate_synthetic_responses",
            None,
            {
                "count": options.count,
                "seed": seed,
                "mode": options.mode,
                "population_revision": state.revision,
            },
        )
        return CampaignResponse(dataset=editor.state, campaign=campaign(connection, survey_id))


def populate_candidate_feedback(connection) -> bool:
    """Seed an immediately demonstrable candidate report from the interview cohort."""
    state = current_dataset(connection)
    start, end = max(state.history_start, "2026-09-01"), state.as_of_date
    exists = connection.execute(
        "SELECT 1 FROM survey_campaigns WHERE id = ?", (TEMPLATE_ID,)
    ).fetchone()
    if exists:
        return False
    samples = _candidate_samples(connection, organisation_id=None, start=start, end=end)
    if start > end or len(samples) < 5:
        return False
    invited = min(24, len(samples))
    count = max(5, invited - 2)
    question = next(q for q in QUESTION_BANK if q["code"] == "candidate")
    connection.execute(
        "INSERT INTO survey_campaigns VALUES (?, ?, ?, ?, ?, ?)",
        (TEMPLATE_ID, SERIES["candidate"], question["prompt"], start, end, invited),
    )
    options = GenerateResponses(
        dataset_id=state.dataset_id,
        dataset_generation=state.dataset_generation,
        count=count,
        mode="balanced",
        analysable_percent=100,
        ambiguous_percent=0,
    )
    connection.execute(
        """
        INSERT INTO voice_campaign_settings
            (survey_id, audience, candidate_audience, series, anonymity_min, taxonomy_version,
             eligible, generated_at, generation_seed, generation_mode, generation_parameters, population_revision)
        VALUES (?, 'employees', 'candidates', 'candidate', 5, ?, ?, ?, 1516, 'balanced', ?, ?)
        """,
        (
            TEMPLATE_ID,
            TAXONOMY_VERSION,
            len(samples),
            f"{end}T00:00:00+00:00",
            options.model_dump_json(exclude={"dataset_id", "dataset_generation"}),
            state.revision,
        ),
    )
    connection.execute(
        "INSERT INTO survey_questions VALUES (?, ?, ?, 'comment', NULL, 0)",
        (TEMPLATE_ID, question["code"], question["prompt"]),
    )
    connection.executemany(
        "INSERT INTO survey_questions VALUES (?, ?, ?, 'rating', 5, ?)",
        [
            (TEMPLATE_ID, key, prompt, order)
            for order, (key, prompt) in enumerate(CANDIDATE_RATINGS, 1)
        ],
    )
    _make_responses(connection, campaign(connection, TEMPLATE_ID), samples, options, 1516)
    return True
