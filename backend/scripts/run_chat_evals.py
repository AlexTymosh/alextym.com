from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "chat_eval_cases.json"
WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґŁłÓóŻżŹźĆćŃńŚś]+|\d+")


@dataclass(frozen=True)
class EvalFailure:
    case_id: str
    check: str
    detail: str


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    suite: str
    category: str
    passed: bool
    failures: tuple[EvalFailure, ...]


def load_eval_cases(path: Path, *, suite: str | None = None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Eval file must contain a 'cases' list.")

    selected_cases = [case for case in cases if suite is None or case.get("suite") == suite]
    for case in selected_cases:
        _validate_case(case)
    return selected_cases


def evaluate_response(case: dict[str, Any], response: dict[str, Any]) -> EvalResult:
    expected = case.get("expected") or {}
    failures: list[EvalFailure] = []
    answer = str(response.get("answer") or "")
    answer_lower = answer.casefold()

    _check_bool(case, response, expected, "not_enough_data", failures)
    _check_bool(case, response, expected, "handoff_suggested", failures)
    _check_exact(case, response, expected, "handoff_reason", failures)
    _check_exact(case, response, expected, "confidence", failures)
    _check_sources(case, response, expected, failures)

    answer_equals = expected.get("answer_equals")
    if isinstance(answer_equals, str) and answer != answer_equals:
        failures.append(_failure(case, "answer_equals", f"Expected exact answer: {answer_equals}"))

    for phrase in _string_list(expected.get("must_include_all")):
        if phrase.casefold() not in answer_lower:
            failures.append(_failure(case, "must_include_all", f"Missing: {phrase}"))

    include_any = _string_list(expected.get("must_include_any"))
    if include_any and not any(item.casefold() in answer_lower for item in include_any):
        failures.append(_failure(case, "must_include_any", f"Missing any of: {include_any}"))

    for phrase in _string_list(expected.get("must_not_include")):
        if phrase.casefold() in answer_lower:
            failures.append(_failure(case, "must_not_include", f"Found: {phrase}"))

    max_words = expected.get("max_words")
    if isinstance(max_words, int) and _word_count(answer) > max_words:
        failures.append(
            _failure(
                case,
                "max_words",
                f"Answer has {_word_count(answer)} words; max is {max_words}.",
            )
        )

    return EvalResult(
        case_id=str(case.get("id")),
        suite=str(case.get("suite")),
        category=str(case.get("category")),
        passed=not failures,
        failures=tuple(failures),
    )


def run_cases(
    cases: Iterable[dict[str, Any]],
    request_chat: Callable[[dict[str, Any]], dict[str, Any]],
) -> list[EvalResult]:
    results: list[EvalResult] = []
    for case in cases:
        payload = {
            "message": case["message"],
            "history": case.get("history", []),
        }
        response = request_chat(payload)
        results.append(evaluate_response(case, response))
    return results


def make_in_process_requester(
    *,
    mode: str,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    from fastapi.testclient import TestClient

    from app.api.chat import get_chat_service
    from app.api.rate_limit import enforce_chat_rate_limit
    from app.main import app
    from app.rag.retriever import EmptyRetriever
    from app.services.chat import ChatService

    app.dependency_overrides.clear()
    app.dependency_overrides[enforce_chat_rate_limit] = lambda: None

    if mode == "isolated":
        app.dependency_overrides[get_chat_service] = lambda: ChatService(retriever=EmptyRetriever())

    client = TestClient(app)

    def request_chat(payload: dict[str, Any]) -> dict[str, Any]:
        response = client.post("/api/chat", json=payload)
        if response.status_code != 200:
            return {
                "answer": f"HTTP {response.status_code}: {response.text}",
                "sources": [],
                "confidence": "low",
                "not_enough_data": True,
                "handoff_suggested": False,
                "handoff_reason": None,
            }
        return dict(response.json())

    return request_chat


def print_report(results: list[EvalResult]) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print(f"Eval result: {passed}/{total} passed")

    by_category: dict[str, list[EvalResult]] = {}
    for result in results:
        by_category.setdefault(result.category, []).append(result)

    for category, category_results in sorted(by_category.items()):
        category_passed = sum(1 for result in category_results if result.passed)
        print(f"- {category}: {category_passed}/{len(category_results)} passed")

    for result in results:
        if result.passed:
            continue
        print(f"\nFAIL {result.case_id}")
        for failure in result.failures:
            print(f"  - {failure.check}: {failure.detail}")


def results_to_dict(results: list[EvalResult]) -> dict[str, Any]:
    return {
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "results": [
            {
                "case_id": result.case_id,
                "suite": result.suite,
                "category": result.category,
                "passed": result.passed,
                "failures": [
                    {
                        "check": failure.check,
                        "detail": failure.detail,
                    }
                    for failure in result.failures
                ],
            }
            for result in results
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run chat/RAG eval cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--suite", default="contract")
    parser.add_argument(
        "--mode",
        choices=("isolated", "live"),
        default="isolated",
        help=(
            "isolated uses EmptyRetriever for deterministic routing checks; "
            "live uses configured OpenAI/Qdrant settings."
        ),
    )
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)

    cases = load_eval_cases(args.cases, suite=args.suite)
    request_chat = make_in_process_requester(mode=args.mode)
    results = run_cases(cases, request_chat)
    print_report(results)

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(results_to_dict(results), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return 0 if all(result.passed for result in results) else 1


def _validate_case(case: dict[str, Any]) -> None:
    required_fields = ("id", "suite", "category", "message", "expected")
    missing_fields = [field for field in required_fields if field not in case]
    if missing_fields:
        raise ValueError(f"Eval case is missing fields: {missing_fields}")
    if not isinstance(case["message"], str) or not case["message"].strip():
        raise ValueError(f"Eval case {case.get('id')} has an invalid message.")
    if not isinstance(case["expected"], dict):
        raise ValueError(f"Eval case {case.get('id')} has invalid expected data.")


def _check_bool(
    case: dict[str, Any],
    response: dict[str, Any],
    expected: dict[str, Any],
    field: str,
    failures: list[EvalFailure],
) -> None:
    if field not in expected:
        return
    if response.get(field) is not expected[field]:
        failures.append(
            _failure(
                case,
                field,
                f"Expected {expected[field]!r}, got {response.get(field)!r}.",
            )
        )


def _check_exact(
    case: dict[str, Any],
    response: dict[str, Any],
    expected: dict[str, Any],
    field: str,
    failures: list[EvalFailure],
) -> None:
    if field not in expected:
        return
    if response.get(field) != expected[field]:
        failures.append(
            _failure(
                case,
                field,
                f"Expected {expected[field]!r}, got {response.get(field)!r}.",
            )
        )


def _check_sources(
    case: dict[str, Any],
    response: dict[str, Any],
    expected: dict[str, Any],
    failures: list[EvalFailure],
) -> None:
    source_expectation = expected.get("sources")
    if source_expectation in (None, "any"):
        return

    sources = response.get("sources") or []
    if source_expectation == "empty" and sources:
        failures.append(_failure(case, "sources", "Expected no sources."))
    elif source_expectation == "non_empty" and not sources:
        failures.append(_failure(case, "sources", "Expected at least one source."))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def _failure(case: dict[str, Any], check: str, detail: str) -> EvalFailure:
    return EvalFailure(
        case_id=str(case.get("id")),
        check=check,
        detail=detail,
    )


if __name__ == "__main__":
    sys.exit(main())
