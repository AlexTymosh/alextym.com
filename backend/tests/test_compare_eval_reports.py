from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_eval_reports import build_markdown, load_report


def test_load_report_reads_case_results(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "case_id": "case-1",
                        "suite": "contract",
                        "category": "handoff",
                        "passed": False,
                        "failures": [
                            {
                                "check": "handoff_suggested",
                                "detail": "Expected True, got False.",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = load_report(report_path)

    assert report["case-1"].category == "handoff"
    assert report["case-1"].passed is False
    assert report["case-1"].failures == ("handoff_suggested: Expected True, got False.",)


def test_build_markdown_marks_fixed_and_regressed_cases(tmp_path: Path) -> None:
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"

    before = {
        "fixed": _case("fixed", False),
        "regressed": _case("regressed", True),
        "same-pass": _case("same-pass", True),
        "same-fail": _case("same-fail", False),
        "removed": _case("removed", True),
    }
    after = {
        "fixed": _case("fixed", True),
        "regressed": _case("regressed", False),
        "same-pass": _case("same-pass", True),
        "same-fail": _case("same-fail", False),
        "added": _case("added", True),
    }

    markdown = build_markdown(
        before_path=before_path,
        after_path=after_path,
        before=before,
        after=after,
    )

    assert "| Passed | 3 | 3 | 0 |" in markdown
    assert "| ✅ Fixed | 1 |" in markdown
    assert "| 🔴 Regressed | 1 |" in markdown
    assert "| fixed | profile | ❌ fail | ✅ pass | ✅ fixed |" in markdown
    assert "| regressed | profile | ✅ pass | ❌ fail | 🔴 regressed |" in markdown
    assert "| added | profile | — | ✅ pass | ➕ added |" in markdown
    assert "| removed | profile | ✅ pass | — | ➖ removed |" in markdown


def _case(case_id: str, passed: bool):
    from scripts.compare_eval_reports import CaseReport

    return CaseReport(
        case_id=case_id,
        suite="contract",
        category="profile",
        passed=passed,
        failures=() if passed else ("missing keyword",),
    )
