from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import AuditActor, Conflict, InvalidOperation, ensure_dataset
from workforce_intelligence.seed import INTERVIEW_SEED
from workforce_intelligence.voice_analysis import (
    AnalyseRequest,
    ClassifiedReport,
    ClassifiedSignal,
    EvidenceItem,
    VoiceProviderTimeout,
    redact,
    run_analysis,
)
from workforce_intelligence.voice_analytics import (
    analyse_survey,
    effective_sample_size,
    priority,
    representation_weights,
)
from workforce_intelligence.voice_campaigns import (
    CampaignCreate,
    GenerateResponses,
    create_campaign,
    generate_responses,
    workspace,
)
from workforce_intelligence.voice_review import (
    ActionCreate,
    ActionUpdate,
    ReviewRequest,
    create_action,
    read_review,
    review_signal,
    update_action,
)

ACTOR = AuditActor("demo-member", "req_voice_test")


@pytest.fixture
def voice_db(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    ensure_dataset(database, INTERVIEW_SEED)
    return database


def epoch(database):
    state = workspace(database).dataset
    return {"dataset_id": state.dataset_id, "dataset_generation": state.dataset_generation}


def create(database, identifier="new-voice", **changes):
    fields = {
        "survey_id": identifier,
        "title": "Career Development and Progression",
        "series": "development",
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "questions": [
            {"code": "feedback", "kind": "comment", "prompt": "How was training access?"},
            {
                "code": "training",
                "kind": "rating",
                "prompt": "I had access to training.",
                "scale_max": 7,
            },
        ],
    }
    return create_campaign(
        database, ACTOR, CampaignCreate(**epoch(database), **{**fields, **changes})
    )


def generate(database, identifier="new-voice", **changes):
    fields = {
        "mode": "significant",
        "count": 15,
        "seed": 32,
        "analysable_percent": 100,
        "positive_percent": 0,
        "negative_percent": 100,
        "theme_percent": 100,
        "ambiguous_percent": 0,
    }
    return generate_responses(
        database, ACTOR, identifier, GenerateResponses(**epoch(database), **{**fields, **changes})
    )


def test_survey_builder_records_population_and_deterministic_responses(voice_db):
    create(voice_db, invited=16)
    create(voice_db, "same-sample", invited=16)
    outcome = generate(voice_db)
    generate(voice_db, "same-sample")
    with voice_db.transaction() as conn:

        def sample(identity):
            return [
                tuple(row)
                for row in conn.execute(
                    """
                SELECT submitted_on, comment, segments, rating
                    FROM survey_responses JOIN voice_response_context context ON context.response_id = id
                JOIN voice_rating_responses rating ON rating.response_id = id
                WHERE survey_id = ? ORDER BY id
            """,
                    (identity,),
                )
            ]

        assert sample("same-sample") == sample("new-voice")
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM survey_response_themes WHERE response_id IN "
                "(SELECT id FROM survey_responses WHERE survey_id = 'new-voice')"
            ).fetchone()[0]
            > 15
        )
        assert conn.execute(
            "SELECT SUM(eligible), SUM(invited) FROM voice_population "
            "WHERE survey_id = 'new-voice' AND dimension = 'clinical'"
        ).fetchone()[:] == (20, 16)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert outcome.campaign["responses"] == outcome.campaign["analysable"] == 15
    assert outcome.campaign["generation_seed"] == 32
    with pytest.raises(Conflict, match="already contains"):
        generate(voice_db)


def test_empty_text_and_invalid_audience_counts_are_handled(voice_db):
    create(voice_db, invited=10)
    with pytest.raises(InvalidOperation, match="cannot exceed"):
        generate(voice_db, count=11)
    result = generate(voice_db, count=10, analysable_percent=0)
    assert result.campaign["responses"] == 10 and result.campaign["analysable"] == 0
    with pytest.raises(InvalidOperation, match="eligible"):
        create(voice_db, "no-exits", audience="exit")
    with voice_db.transaction() as conn:
        count = conn.execute(
            """
            SELECT COUNT(*) FROM survey_response_themes theme
            JOIN survey_responses response ON response.id = theme.response_id
            WHERE response.survey_id = 'new-voice'
            """
        ).fetchone()[0]
        assert count == 0


def test_weighting_uses_true_population_shares_and_trimmed_effective_size():
    weights = representation_weights({"A": 80, "B": 20}, {"A": 10, "B": 15}, 0.5, 2, 5)
    assert weights == {"A": 2, "B": 0.5}
    assert effective_sample_size([2, 2, 0.5, 0.5]) == 2.94
    assert representation_weights({"A": 95, "B": 5}, {"A": 20}, 0.5, 2, 5) is None
    score = priority("safety", "Critical", 20, concentration=10, trend=5)
    assert score["score"] == 59
    assert score["priority_human_review"]


def test_generated_theme_totals_reconcile_and_small_partitions_are_hidden(voice_db):
    create(voice_db)
    generate(voice_db)
    report = analyse_survey(
        voice_db, "new-voice", "organisation", "service", "safety", 0.5, 2
    ).report
    assert report["segments"] == [] and report["segments_suppressed"]
    assert report["minimum"] == 5
    assert report["requires_human_attention"]
    for row in report["theme_frequencies"]:
        with voice_db.transaction() as conn:
            count, mentions = conn.execute(
                "SELECT COUNT(DISTINCT response_id), COUNT(*) FROM survey_response_themes WHERE theme = ?",
                (row["theme"],),
            ).fetchone()
        assert (row["responses"], row["mentions"]) == (count, mentions)
    with pytest.raises(InvalidOperation, match="approved"):
        analyse_survey(voice_db, "new-voice", "organisation,role", "service", "safety", 0.5, 2)


def analyse(database, mode="demo", provider=None, identifier="new-voice", key=None):
    command = AnalyseRequest(**epoch(database), mode=mode, idempotency_key=key or uuid4())
    return run_analysis(database, ACTOR, identifier, command, provider)


def review(database, identity, action, **fields):
    return review_signal(
        database,
        ACTOR,
        identity,
        ReviewRequest(
            **epoch(database),
            action=action,
            rationale="Reviewed the synthetic evidence against the report scope.",
            **fields,
        ),
    )


class Classifier:
    name = "test-provider"
    model = "structured-test"

    def __init__(self, mode):
        self.mode = mode
        self.received = []

    def classify(self, question, comments):
        self.received.append((question, comments))
        if self.mode == "outage":
            raise RuntimeError("Do not surface provider error details")
        if self.mode == "timeout":
            raise VoiceProviderTimeout("Do not surface timeout details")
        evidence = [
            EvidenceItem(response_id=row["response_id"], excerpt=row["comment"][:100])
            for row in comments[: 1 if self.mode == "small" else 7]
        ]
        if self.mode == "invented":
            evidence[0].response_id = "fake-response"
        if self.mode == "unsupported":
            evidence[0].excerpt = "Invented evidence should never be published."
        signal = ClassifiedSignal(
            theme="safety",
            subtheme=None,
            classification="Safety concern",
            severity="Critical",
            summary="Potential safety signal requires review.",
            evidence=evidence,
            unique_response_count=len(evidence) + int(self.mode == "bad-count"),
            priority_human_review=True,
        )
        return ClassifiedReport(
            summary="Classification returned; check the evidence before making a decision.",
            signals=[signal],
        )


@pytest.mark.parametrize(
    ("mode", "failure"),
    [
        ("invented", "evidence_validation_failed"),
        ("unsupported", "evidence_validation_failed"),
        ("bad-count", "evidence_validation_failed"),
        ("outage", "provider_unavailable"),
        ("timeout", "provider_timeout"),
    ],
)
def test_invalid_provider_runs_do_not_create_findings_and_retry_is_idempotent(
    voice_db, mode, failure
):
    create(voice_db)
    generate(voice_db)
    fake = Classifier(mode)
    key = uuid4()
    result = analyse(voice_db, "ai", fake, key=key)
    assert result.run["status"] == "failed"
    assert result.run["failure"] == failure
    again = analyse(voice_db, "ai", fake, key=key)
    assert again.run == result.run and len(fake.received) == 1
    assert read_review(voice_db, "new-voice", result.run["id"]).signals == []
    with voice_db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM gold_voice_published_findings").fetchone()[0] == 0


def test_demo_and_human_gates_allow_a_published_finding_and_closed_action(voice_db):
    create(voice_db)
    generate(voice_db)
    result = analyse(voice_db)
    assert (
        result.run["status"] == "ready" and result.run["label"] == "Demonstration fallback result"
    )
    view = read_review(voice_db, "new-voice", result.run["id"])
    signal = next(item for item in view.signals if item["publication_eligible"])
    identity = signal["id"]
    with pytest.raises(InvalidOperation, match="before publishing"):
        review(voice_db, identity, "publish")
    with pytest.raises(InvalidOperation, match="validated evidence"):
        review(voice_db, identity, "amend", keep_response_ids=["does-not-exist"])
    reviewed = review(voice_db, identity, "amend", classification="Concern")
    assert next(item for item in reviewed.signals if item["id"] == identity)["state"] == "amended"
    with voice_db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM gold_voice_published_findings").fetchone()[0] == 0
    review(voice_db, identity, "publish")
    with voice_db.transaction() as conn:
        assert (
            conn.execute("SELECT id FROM gold_voice_published_findings").fetchone()[0] == identity
        )
    payload = {
        "title": "Pilot equipment checklist",
        "team": "Operations",
        "baseline": "Inconsistent checks",
        "target": "Complete the demo checklist each shift",
        "expected_benefit": "Earlier issue discovery",
        "due_on": datetime.now(UTC).date() + timedelta(days=14),
    }
    tracker = create_action(voice_db, ACTOR, identity, ActionCreate(**epoch(voice_db), **payload))
    action = tracker.actions[0]
    assert action["status"] == "open"
    update_action(
        voice_db,
        ACTOR,
        action["id"],
        ActionUpdate(**epoch(voice_db), status="in_progress", notes="Synthetic pilot started."),
    )
    closed = update_action(
        voice_db,
        ACTOR,
        action["id"],
        ActionUpdate(
            **epoch(voice_db),
            status="closed",
            notes="Synthetic pilot completed.",
            closure_evidence="Example checklist and audit reviewed.",
        ),
    )
    assert closed.actions[0]["status"] == "closed"
    assert closed.actions[0]["closure_evidence"]


def test_small_signals_redact_identity_like_text_and_cannot_publish(voice_db):
    create(voice_db)
    generate(voice_db)
    fake = Classifier("small")
    first = analyse(voice_db, "ai", fake)
    view = read_review(voice_db, "new-voice", first.run["id"])
    assert first.run["status"] == "ready"
    assert view.selected_run.get("summary") is None
    signal = view.signals[0]
    assert signal["urgent"] and signal["theme_code"] is None
    assert signal["evidence"] == [] and signal["unique_responses"] is None
    review(voice_db, signal["id"], "confirm")
    with pytest.raises(InvalidOperation, match="anonymity"):
        review(voice_db, signal["id"], "publish")
    cleaned = redact(
        "Contact Dr Alex Example, staff-1234, test@example.invalid or +44 1234 555 123."
    )
    assert all(value not in cleaned for value in ("Alex", "Example", "1234", "@"))
