from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.rag.factory import get_configured_retriever
from app.rag.models import KnowledgeChunk
from scripts.compare_eval_reports import build_markdown
from scripts.compare_eval_reports import compare_summary
from scripts.compare_eval_reports import load_report
from scripts.compare_eval_reports import load_report_metadata

DEFAULT_CASES_PATH = (
    Path(__file__).resolve().parents[1] / "evals" / "retrieval_eval_cases_generated_rag.json"
)


@dataclass(frozen=True)
class RetrievalEvalFailure:
    check: str
    detail: str


@dataclass(frozen=True)
class RetrievalEvalResult:
    case_id: str
    suite: str
    category: str
    query: str
    passed: bool
    failures: tuple[RetrievalEvalFailure, ...]
    retrieved: tuple[dict[str, object], ...]


def run_retrieval_eval_cycle(
    *,
    cases_path: Path,
    suite: str,
    before_path: Path,
    after_path: Path,
    comparison_path: Path,
    limit: int,
    allow_failures: bool = False,
    retriever: object | None = None,
) -> int:
    had_previous_after = _has_report(after_path)

    if had_previous_after:
        _rotate_after_to_before(before_path=before_path, after_path=after_path)

    resolved_retriever = retriever or get_configured_retriever()
    cases = load_retrieval_eval_cases(cases_path, suite=suite)
    results = run_cases(cases, retriever=resolved_retriever, default_limit=limit)
    _write_json(
        after_path,
        results_to_dict(
            results,
            metadata={
                "suite": suite,
                "mode": "live-retrieval",
                "cases_path": cases_path.as_posix(),
                "report_path": after_path.as_posix(),
                "comparison_path": comparison_path.as_posix(),
                "limit": limit,
            },
        ),
    )
    print_report(results)

    all_passed = all(result.passed for result in results)
    if not had_previous_after:
        print("")
        print("Retrieval baseline eval completed.")
        print(f"Results written to: {after_path}")
        print("No previous after-report existed, so comparison was not created.")
        return _exit_code(
            all_passed=all_passed,
            regressed=0,
            allow_failures=allow_failures,
        )

    before = load_report(before_path)
    after = load_report(after_path)
    markdown = build_markdown(
        before_path=before_path,
        after_path=after_path,
        before=before,
        after=after,
        before_metadata=load_report_metadata(before_path),
        after_metadata=load_report_metadata(after_path),
    )
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.write_text(markdown, encoding="utf-8")

    summary = compare_summary(before=before, after=after)
    print("")
    print("Retrieval eval cycle completed.")
    print(f"Previous after-report moved to: {before_path}")
    print(f"New results written to: {after_path}")
    print(f"Comparison written to: {comparison_path}")
    print(
        "Before: "
        f"{summary.before_passed}/{summary.before_total} passed; "
        "After: "
        f"{summary.after_passed}/{summary.after_total} passed"
    )
    print(f"Fixed: {summary.fixed}; regressed: {summary.regressed}")

    return _exit_code(
        all_passed=all_passed,
        regressed=summary.regressed,
        allow_failures=allow_failures,
    )


def load_retrieval_eval_cases(
    path: Path,
    *,
    suite: str | None = None,
) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Retrieval eval file must contain a 'cases' list.")

    selected_cases = [case for case in cases if suite is None or case.get("suite") == suite]
    for case in selected_cases:
        _validate_case(case)
    return selected_cases


def run_cases(
    cases: Iterable[dict[str, Any]],
    *,
    retriever: object,
    default_limit: int,
) -> list[RetrievalEvalResult]:
    return [
        evaluate_case(
            case,
            chunks=_retrieve_case(
                case,
                retriever=retriever,
                default_limit=default_limit,
            ),
        )
        for case in cases
    ]


def evaluate_case(
    case: dict[str, Any],
    *,
    chunks: list[KnowledgeChunk],
) -> RetrievalEvalResult:
    expected = case.get("expected") or {}
    retrieved = tuple(_chunk_snapshot(chunk, rank=index + 1) for index, chunk in enumerate(chunks))
    failures: list[RetrievalEvalFailure] = []

    _check_min_results(expected, retrieved, failures)
    _check_top_topic(expected, retrieved, failures)
    _check_topic_any(expected, retrieved, failures)
    _check_tag_any(expected, retrieved, failures)
    _check_section_any(expected, retrieved, failures)
    _check_source_any(expected, retrieved, failures)
    _check_forbidden_topics(expected, retrieved, failures)

    return RetrievalEvalResult(
        case_id=str(case["id"]),
        suite=str(case["suite"]),
        category=str(case["category"]),
        query=str(case["query"]),
        passed=not failures,
        failures=tuple(failures),
        retrieved=retrieved,
    )


def results_to_dict(
    results: list[RetrievalEvalResult],
    *,
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "metadata": _report_metadata(metadata),
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "results": [
            {
                "case_id": result.case_id,
                "suite": result.suite,
                "category": result.category,
                "query": result.query,
                "passed": result.passed,
                "failures": [
                    {
                        "check": failure.check,
                        "detail": failure.detail,
                    }
                    for failure in result.failures
                ],
                "retrieved": list(result.retrieved),
            }
            for result in results
        ],
    }


def print_report(results: list[RetrievalEvalResult]) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print(f"Retrieval eval result: {passed}/{total} passed")

    by_category: dict[str, list[RetrievalEvalResult]] = {}
    for result in results:
        by_category.setdefault(result.category, []).append(result)

    for category, category_results in sorted(by_category.items()):
        category_passed = sum(1 for result in category_results if result.passed)
        print(f"- {category}: {category_passed}/{len(category_results)} passed")

    for result in results:
        if result.passed:
            continue
        print(f"\nFAIL {result.case_id}")
        print(f"  query: {result.query}")
        for failure in result.failures:
            print(f"  - {failure.check}: {failure.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run retrieval-level RAG evals with before/after rotation."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Write reports even when retrieval eval cases fail.",
    )
    args = parser.parse_args(argv)

    return run_retrieval_eval_cycle(
        cases_path=args.cases,
        suite=args.suite,
        before_path=args.before,
        after_path=args.after,
        comparison_path=args.comparison,
        limit=args.limit,
        allow_failures=args.allow_failures,
    )


def _retrieve_case(
    case: dict[str, Any],
    *,
    retriever: object,
    default_limit: int,
) -> list[KnowledgeChunk]:
    limit = case.get("limit")
    resolved_limit = limit if isinstance(limit, int) and limit > 0 else default_limit
    chunks = retriever.retrieve(str(case["query"]), limit=resolved_limit)
    return list(chunks)


def _validate_case(case: dict[str, Any]) -> None:
    required_fields = ("id", "suite", "category", "query", "expected")
    missing_fields = [field for field in required_fields if field not in case]
    if missing_fields:
        raise ValueError(f"Retrieval eval case is missing fields: {missing_fields}")
    if not isinstance(case["query"], str) or not case["query"].strip():
        raise ValueError(f"Retrieval eval case {case.get('id')} has invalid query.")
    if not isinstance(case["expected"], dict):
        raise ValueError(f"Retrieval eval case {case.get('id')} has invalid expected data.")


def _check_min_results(
    expected: dict[str, Any],
    retrieved: tuple[dict[str, object], ...],
    failures: list[RetrievalEvalFailure],
) -> None:
    min_results = expected.get("min_results")
    if not isinstance(min_results, int):
        return
    if len(retrieved) < min_results:
        failures.append(
            RetrievalEvalFailure(
                check="min_results",
                detail=(f"Expected at least {min_results} result(s), got {len(retrieved)}."),
            )
        )


def _check_top_topic(
    expected: dict[str, Any],
    retrieved: tuple[dict[str, object], ...],
    failures: list[RetrievalEvalFailure],
) -> None:
    expected_topics = _string_list(expected.get("top_topic_any"))
    if not expected_topics or not retrieved:
        return

    actual_topic = str(retrieved[0].get("topic") or "")
    if actual_topic not in expected_topics:
        failures.append(
            RetrievalEvalFailure(
                check="top_topic_any",
                detail=(f"Expected top topic in {expected_topics}, got {actual_topic!r}."),
            )
        )


def _check_topic_any(
    expected: dict[str, Any],
    retrieved: tuple[dict[str, object], ...],
    failures: list[RetrievalEvalFailure],
) -> None:
    expected_topics = _string_list(expected.get("must_include_topic_any"))
    if not expected_topics:
        return

    actual_topics = {str(chunk.get("topic") or "") for chunk in retrieved}
    if not actual_topics.intersection(expected_topics):
        failures.append(
            RetrievalEvalFailure(
                check="must_include_topic_any",
                detail=(f"Expected any topic from {expected_topics}, got {sorted(actual_topics)}."),
            )
        )


def _check_tag_any(
    expected: dict[str, Any],
    retrieved: tuple[dict[str, object], ...],
    failures: list[RetrievalEvalFailure],
) -> None:
    expected_tags = _string_list(expected.get("must_include_tag_any"))
    if not expected_tags:
        return

    actual_tags = _all_retrieved_tags(retrieved)
    if not actual_tags.intersection(expected_tags):
        failures.append(
            RetrievalEvalFailure(
                check="must_include_tag_any",
                detail=(f"Expected any tag from {expected_tags}, got {sorted(actual_tags)}."),
            )
        )


def _check_section_any(
    expected: dict[str, Any],
    retrieved: tuple[dict[str, object], ...],
    failures: list[RetrievalEvalFailure],
) -> None:
    expected_sections = _string_list(expected.get("must_include_section_any"))
    if not expected_sections:
        return

    actual_sections = {str(chunk.get("section") or "") for chunk in retrieved}
    if not actual_sections.intersection(expected_sections):
        failures.append(
            RetrievalEvalFailure(
                check="must_include_section_any",
                detail=(
                    f"Expected any section from {expected_sections}, got {sorted(actual_sections)}."
                ),
            )
        )


def _check_source_any(
    expected: dict[str, Any],
    retrieved: tuple[dict[str, object], ...],
    failures: list[RetrievalEvalFailure],
) -> None:
    expected_sources = _string_list(expected.get("must_include_source_any"))
    if not expected_sources:
        return

    actual_sources = {str(chunk.get("source") or "") for chunk in retrieved}
    if not actual_sources.intersection(expected_sources):
        failures.append(
            RetrievalEvalFailure(
                check="must_include_source_any",
                detail=(
                    f"Expected any source from {expected_sources}, got {sorted(actual_sources)}."
                ),
            )
        )


def _check_forbidden_topics(
    expected: dict[str, Any],
    retrieved: tuple[dict[str, object], ...],
    failures: list[RetrievalEvalFailure],
) -> None:
    forbidden_topics = set(_string_list(expected.get("must_not_include_topic")))
    if not forbidden_topics:
        return

    actual_topics = {str(chunk.get("topic") or "") for chunk in retrieved}
    found_topics = sorted(actual_topics.intersection(forbidden_topics))
    if found_topics:
        failures.append(
            RetrievalEvalFailure(
                check="must_not_include_topic",
                detail=f"Found forbidden topic(s): {found_topics}.",
            )
        )


def _chunk_snapshot(chunk: KnowledgeChunk, *, rank: int) -> dict[str, object]:
    return {
        "rank": rank,
        "id": chunk.id,
        "source": chunk.metadata.source,
        "section": chunk.metadata.section,
        "topic": chunk.metadata.topic,
        "visibility": chunk.metadata.visibility,
        "tags": list(chunk.metadata.tags),
        "content_preview": chunk.content[:240],
    }


def _all_retrieved_tags(retrieved: tuple[dict[str, object], ...]) -> set[str]:
    tags: set[str] = set()
    for chunk in retrieved:
        raw_tags = chunk.get("tags") or []
        if not isinstance(raw_tags, list):
            continue
        tags.update(str(tag) for tag in raw_tags)
    return tags


def _has_report(path: Path) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload.get("results"), list)


def _rotate_after_to_before(*, before_path: Path, after_path: Path) -> None:
    before_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(after_path, before_path)
    after_path.write_text("", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _report_metadata(metadata: dict[str, object] | None) -> dict[str, object]:
    local_now = datetime.now().astimezone()
    utc_now = local_now.astimezone(UTC)
    return {
        "generated_at_local": local_now.isoformat(timespec="seconds"),
        "generated_at_utc": utc_now.isoformat(timespec="seconds"),
        **(metadata or {}),
    }


def _exit_code(
    *,
    all_passed: bool,
    regressed: int,
    allow_failures: bool,
) -> int:
    if allow_failures:
        return 0
    return 0 if all_passed and regressed == 0 else 1


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


if __name__ == "__main__":
    sys.exit(main())
