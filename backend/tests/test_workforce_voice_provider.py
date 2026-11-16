from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import APITimeoutError
from workforce_intelligence.dataset import InvalidOperation
from workforce_intelligence.voice_analysis import VoiceProviderTimeout, validate_evidence

from app.core.config import get_settings
from app.llm import workforce_voice

COMMENTS = [
    {"response_id": "r-1", "comment": "I had no time for training. The course was cancelled."},
    {"response_id": "r-2", "comment": "Training was cancelled twice."},
]


@pytest.fixture
def provider(monkeypatch):
    parse = Mock()
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    monkeypatch.setattr(workforce_voice, "OpenAI", Mock(return_value=client))
    settings = replace(get_settings(), openai_api_key="test-key", openai_model="gpt-5-mini")
    return workforce_voice.WorkforceVoiceOpenAI(settings), parse


def selected(*labels):
    signal = workforce_voice.EvidenceSelection(
        theme="development",
        subtheme=None,
        classification="Concern",
        severity="Medium",
        summary="Staff report interruptions to training.",
        priority_human_review=False,
        evidence_ids=list(labels),
    )
    return SimpleNamespace(
        output_parsed=workforce_voice.SelectedReport(summary="Training feedback.", signals=[signal])
    )


def test_provider_resolves_literal_excerpts_and_counts_responses_once(provider):
    classifier, parse = provider
    parse.return_value = selected("e-2", "e-1", "e-3")
    report = classifier.classify("What affected training?", COMMENTS)
    validate_evidence(report, {row["response_id"]: row["comment"] for row in COMMENTS})
    (signal,) = report.signals
    assert [(item.response_id, item.excerpt) for item in signal.evidence] == [
        ("r-1", "The course was cancelled."),
        ("r-2", "Training was cancelled twice."),
    ]
    assert signal.unique_response_count == 2


def test_provider_rejects_an_unknown_excerpt_id(provider):
    classifier, parse = provider
    parse.return_value = selected("e-1", "e-99")
    with pytest.raises(InvalidOperation, match="unknown evidence ID"):
        classifier.classify("What affected training?", COMMENTS)


def test_provider_preserves_the_timeout_category(provider):
    classifier, parse = provider
    parse.side_effect = APITimeoutError(
        request=httpx.Request("POST", "https://api.openai.com/v1/responses")
    )
    with pytest.raises(VoiceProviderTimeout):
        classifier.classify("What affected training?", COMMENTS)
