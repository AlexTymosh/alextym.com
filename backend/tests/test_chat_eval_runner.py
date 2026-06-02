from __future__ import annotations

import json
from pathlib import Path

from scripts.run_chat_evals import evaluate_response
from scripts.run_chat_evals import load_eval_cases
from scripts.run_chat_evals import results_to_dict
from scripts.run_chat_evals import run_cases


def test_evaluate_response_passes_matching_expectations() -> None:
    case = {
        "id": "case-1",
        "suite": "contract",
        "category": "handoff",
        "message": "connect me",
        "expected": {
            "not_enough_data": False,
            "handoff_suggested": True,
            "handoff_reason": "user_requested_human",
            "sources": "empty",
            "must_include_all": ["connect"],
            "must_not_include": ["medical advice"],
            "max_words": 20,
        },
    }
    response = {
        "answer": "I can help connect you with the site owner.",
        "sources": [],
        "confidence": "medium",
        "not_enough_data": False,
        "handoff_suggested": True,
        "handoff_reason": "user_requested_human",
    }

    result = evaluate_response(case, response)

    assert result.passed is True
    assert result.failures == ()


def test_evaluate_response_reports_failed_expectations() -> None:
    case = {
        "id": "case-2",
        "suite": "contract",
        "category": "out_of_scope",
        "message": "How can I take pills?",
        "expected": {
            "handoff_suggested": False,
            "sources": "empty",
            "must_not_include": ["dose"],
            "max_words": 3,
        },
    }
    response = {
        "answer": "Take the dose with water.",
        "sources": [{"title": "x", "confidence": "medium"}],
        "confidence": "medium",
        "not_enough_data": False,
        "handoff_suggested": True,
        "handoff_reason": None,
    }

    result = evaluate_response(case, response)

    assert result.passed is False
    failed_checks = {failure.check for failure in result.failures}
    assert failed_checks == {
        "handoff_suggested",
        "sources",
        "must_not_include",
        "max_words",
    }


def test_load_eval_cases_filters_by_suite(tmp_path: Path) -> None:
    eval_file = tmp_path / "cases.json"
    eval_file.write_text(
        json.dumps(
            {
                "version": 1,
                "cases": [
                    {
                        "id": "contract-1",
                        "suite": "contract",
                        "category": "greeting",
                        "message": "Hi",
                        "expected": {},
                    },
                    {
                        "id": "rag-1",
                        "suite": "rag_quality",
                        "category": "profile",
                        "message": "Tell me about the site owner",
                        "expected": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    cases = load_eval_cases(eval_file, suite="contract")

    assert [case["id"] for case in cases] == ["contract-1"]


def test_bundled_eval_cases_are_schema_valid() -> None:
    eval_file = Path(__file__).resolve().parents[1] / "evals" / "chat_eval_cases.json"

    cases = load_eval_cases(eval_file)

    assert len(cases) >= 25
    assert all(case["id"] for case in cases)


def test_results_to_dict_adds_timestamp_metadata() -> None:
    case = {
        "id": "case-4",
        "suite": "contract",
        "category": "greeting",
        "message": "Hi",
        "expected": {"not_enough_data": False},
    }
    response = {
        "answer": "Assistant ready.",
        "sources": [],
        "confidence": "medium",
        "not_enough_data": False,
        "handoff_suggested": False,
        "handoff_reason": None,
    }

    result = evaluate_response(case, response)
    payload = results_to_dict(
        [result],
        metadata={
            "suite": "contract",
            "mode": "isolated",
            "cases_path": "evals/chat_eval_cases.json",
        },
    )

    assert payload["metadata"]["suite"] == "contract"
    assert payload["metadata"]["mode"] == "isolated"
    assert payload["metadata"]["generated_at_local"]
    assert payload["metadata"]["generated_at_utc"]
    assert payload["results"][0]["case_id"] == "case-4"


def test_run_cases_uses_request_callable() -> None:
    cases = [
        {
            "id": "case-3",
            "suite": "contract",
            "category": "greeting",
            "message": "Hi",
            "expected": {
                "not_enough_data": False,
                "sources": "empty",
                "must_include_all": ["assistant"],
            },
        }
    ]

    def request_chat(payload: dict[str, object]) -> dict[str, object]:
        assert payload["message"] == "Hi"
        return {
            "answer": "Assistant ready.",
            "sources": [],
            "confidence": "medium",
            "not_enough_data": False,
            "handoff_suggested": False,
            "handoff_reason": None,
        }

    results = run_cases(cases, request_chat)

    assert len(results) == 1
    assert results[0].passed is True
