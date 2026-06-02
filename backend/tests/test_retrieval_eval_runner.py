from __future__ import annotations

import json
from pathlib import Path


from app.rag.models import ChunkMetadata, KnowledgeChunk
from scripts.run_retrieval_evals import _has_report
from scripts.run_retrieval_evals import _rotate_after_to_before
from scripts.run_retrieval_evals import evaluate_case
from scripts.run_retrieval_evals import load_retrieval_eval_cases
from scripts.run_retrieval_evals import results_to_dict
from scripts.run_retrieval_evals import run_retrieval_eval_cycle


def test_load_retrieval_eval_cases_filters_by_suite(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            {
                "cases": [
                    _case("case-1", suite="rag_retrieval_quality"),
                    _case("case-2", suite="other"),
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = load_retrieval_eval_cases(
        cases_path,
        suite="rag_retrieval_quality",
    )

    assert [case["id"] for case in cases] == ["case-1"]


def test_bundled_retrieval_eval_cases_are_schema_valid() -> None:
    cases_path = (
        Path(__file__).resolve().parents[1] / "evals" / "retrieval_eval_cases_generated_rag.json"
    )

    cases = load_retrieval_eval_cases(
        cases_path,
        suite="rag_retrieval_quality",
    )

    assert len(cases) == 8
    assert all(case["expected"] for case in cases)


def test_evaluate_case_passes_expected_topic_and_tag() -> None:
    case = _case(
        "hard-skills",
        expected={
            "min_results": 1,
            "top_topic_any": ["hard-skills"],
            "must_include_topic_any": ["hard-skills"],
            "must_include_tag_any": ["python"],
        },
    )

    result = evaluate_case(
        case,
        chunks=[
            _chunk(
                "chunk-1",
                topic="hard-skills",
                tags=("hard-skills", "python"),
            )
        ],
    )

    assert result.passed is True
    assert result.retrieved[0]["topic"] == "hard-skills"


def test_evaluate_case_reports_missing_topic_and_tag() -> None:
    case = _case(
        "soft-skills",
        expected={
            "min_results": 1,
            "top_topic_any": ["soft-skills-working-style"],
            "must_include_topic_any": ["soft-skills-working-style"],
            "must_include_tag_any": ["soft-skills"],
        },
    )

    result = evaluate_case(
        case,
        chunks=[_chunk("chunk-1", topic="hard-skills", tags=("python",))],
    )

    failed_checks = {failure.check for failure in result.failures}

    assert result.passed is False
    assert failed_checks == {
        "top_topic_any",
        "must_include_topic_any",
        "must_include_tag_any",
    }


def test_results_to_dict_includes_metadata_and_retrieved_chunks() -> None:
    result = evaluate_case(
        _case("case-1"),
        chunks=[_chunk("chunk-1", topic="hard-skills", tags=("python",))],
    )

    payload = results_to_dict(
        [result],
        metadata={"suite": "rag_retrieval_quality", "mode": "live-retrieval"},
    )

    assert payload["metadata"]["generated_at_local"]
    assert payload["metadata"]["generated_at_utc"]
    assert payload["metadata"]["suite"] == "rag_retrieval_quality"
    assert payload["results"][0]["retrieved"][0]["topic"] == "hard-skills"


def test_run_retrieval_eval_cycle_creates_baseline_without_comparison(
    tmp_path: Path,
) -> None:
    cases_path = _cases_file(tmp_path)
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    comparison = tmp_path / "comparison.md"

    exit_code = run_retrieval_eval_cycle(
        cases_path=cases_path,
        suite="rag_retrieval_quality",
        before_path=before,
        after_path=after,
        comparison_path=comparison,
        limit=6,
        retriever=FakeRetriever([_chunk("chunk-1", topic="hard-skills")]),
    )

    assert exit_code == 0
    assert after.exists()
    assert not before.exists()
    assert not comparison.exists()


def test_run_retrieval_eval_cycle_rotates_and_compares(
    tmp_path: Path,
) -> None:
    cases_path = _cases_file(tmp_path)
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    comparison = tmp_path / "comparison.md"
    after.write_text(
        json.dumps(
            {
                "metadata": {
                    "generated_at_local": "2026-06-01T12:00:00+01:00",
                    "suite": "rag_retrieval_quality",
                    "mode": "live-retrieval",
                },
                "results": [
                    {
                        "case_id": "case-1",
                        "suite": "rag_retrieval_quality",
                        "category": "skills",
                        "passed": False,
                        "failures": [
                            {
                                "check": "must_include_topic_any",
                                "detail": "Missing topic.",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = run_retrieval_eval_cycle(
        cases_path=cases_path,
        suite="rag_retrieval_quality",
        before_path=before,
        after_path=after,
        comparison_path=comparison,
        limit=6,
        retriever=FakeRetriever([_chunk("chunk-1", topic="hard-skills")]),
    )

    comparison_text = comparison.read_text(encoding="utf-8")

    assert exit_code == 0
    assert before.exists()
    assert after.exists()
    assert "✅ fixed" in comparison_text
    assert "2026-06-01T12:00:00+01:00" in comparison_text


def test_run_retrieval_eval_cycle_allows_failures_for_measurement(
    tmp_path: Path,
) -> None:
    cases_path = _cases_file(tmp_path)
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    comparison = tmp_path / "comparison.md"

    exit_code = run_retrieval_eval_cycle(
        cases_path=cases_path,
        suite="rag_retrieval_quality",
        before_path=before,
        after_path=after,
        comparison_path=comparison,
        limit=6,
        allow_failures=True,
        retriever=FakeRetriever([_chunk("chunk-1", topic="wrong-topic")]),
    )

    assert exit_code == 0
    assert after.exists()
    assert not before.exists()
    assert not comparison.exists()


def test_has_report_returns_false_for_missing_empty_or_invalid_file(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"
    empty = tmp_path / "empty.json"
    invalid = tmp_path / "invalid.json"
    empty.write_text("", encoding="utf-8")
    invalid.write_text("{not-json", encoding="utf-8")

    assert _has_report(missing) is False
    assert _has_report(empty) is False
    assert _has_report(invalid) is False


def test_rotate_after_to_before_copies_after_and_clears_after(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    after.write_text('{"results": []}\n', encoding="utf-8")

    _rotate_after_to_before(before_path=before, after_path=after)

    assert before.read_text(encoding="utf-8") == '{"results": []}\n'
    assert after.read_text(encoding="utf-8") == ""


class FakeRetriever:
    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks
        self.last_query: str | None = None
        self.last_limit: int | None = None

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        self.last_query = query
        self.last_limit = limit
        return self.chunks[:limit]


def _cases_file(tmp_path: Path) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    _case(
                        "case-1",
                        expected={
                            "min_results": 1,
                            "must_include_topic_any": ["hard-skills"],
                        },
                    )
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _case(
    case_id: str,
    *,
    suite: str = "rag_retrieval_quality",
    expected: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": case_id,
        "suite": suite,
        "category": "skills",
        "query": "What are Alex's hard skills?",
        "expected": expected
        or {
            "min_results": 1,
            "must_include_topic_any": ["hard-skills"],
        },
    }


def _chunk(
    chunk_id: str,
    *,
    topic: str,
    tags: tuple[str, ...] = (),
    section: str = "experience",
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        content="Alex uses Python.",
        metadata=ChunkMetadata(
            source="Hard Skills",
            section=section,
            topic=topic,
            tags=tags,
        ),
    )
