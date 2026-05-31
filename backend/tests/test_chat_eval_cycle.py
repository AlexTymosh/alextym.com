from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_chat_eval_cycle import _has_report
from scripts.run_chat_eval_cycle import _rotate_after_to_before
from scripts.run_chat_eval_cycle import run_eval_cycle


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


def test_has_report_returns_true_for_eval_report(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"results": [{"case_id": "case-1"}]}),
        encoding="utf-8",
    )

    assert _has_report(report) is True


def test_rotate_after_to_before_copies_after_and_clears_after(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    after.write_text('{"results": []}\n', encoding="utf-8")

    _rotate_after_to_before(before_path=before, after_path=after)

    assert before.read_text(encoding="utf-8") == '{"results": []}\n'
    assert after.read_text(encoding="utf-8") == ""


def test_run_eval_cycle_creates_initial_after_without_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases_path = _cases_file(tmp_path)
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    comparison = tmp_path / "comparison.md"

    _patch_successful_eval(monkeypatch)

    exit_code = run_eval_cycle(
        cases_path=cases_path,
        suite="contract",
        mode="isolated",
        before_path=before,
        after_path=after,
        comparison_path=comparison,
    )

    assert exit_code == 0
    assert after.exists()
    assert not before.exists()
    assert not comparison.exists()


def test_run_eval_cycle_rotates_previous_after_and_writes_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases_path = _cases_file(tmp_path)
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    comparison = tmp_path / "comparison.md"
    after.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "case_id": "case-1",
                        "suite": "contract",
                        "category": "greeting",
                        "passed": False,
                        "failures": [
                            {
                                "check": "must_include_all",
                                "detail": "Missing: assistant",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    _patch_successful_eval(monkeypatch)

    exit_code = run_eval_cycle(
        cases_path=cases_path,
        suite="contract",
        mode="isolated",
        before_path=before,
        after_path=after,
        comparison_path=comparison,
    )

    assert exit_code == 0
    assert before.exists()
    assert after.exists()
    assert comparison.exists()
    assert "✅ fixed" in comparison.read_text(encoding="utf-8")


def _cases_file(tmp_path: Path) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "case-1",
                        "suite": "contract",
                        "category": "greeting",
                        "message": "Hi",
                        "expected": {
                            "not_enough_data": False,
                            "must_include_all": ["assistant"],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _patch_successful_eval(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_requester(*, mode: str):
        assert mode == "isolated"

        def request_chat(payload: dict[str, object]) -> dict[str, object]:
            return {
                "answer": "Assistant ready.",
                "sources": [],
                "confidence": "medium",
                "not_enough_data": False,
                "handoff_suggested": False,
                "handoff_reason": None,
            }

        return request_chat

    monkeypatch.setattr(
        "scripts.run_chat_eval_cycle.make_in_process_requester",
        fake_requester,
    )
