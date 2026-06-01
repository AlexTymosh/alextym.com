from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CaseReport:
    case_id: str
    suite: str
    category: str
    passed: bool
    failures: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonSummary:
    before_total: int
    before_passed: int
    before_failed: int
    after_total: int
    after_passed: int
    after_failed: int
    fixed: int
    regressed: int
    unchanged_passed: int
    unchanged_failed: int
    added: int
    removed: int


def load_report(path: Path) -> dict[str, CaseReport]:
    payload = _load_report_payload(path)
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError(f"{path} does not contain a 'results' list.")

    report: dict[str, CaseReport] = {}
    for item in results:
        case_id = str(item.get("case_id") or "")
        if not case_id:
            raise ValueError(f"{path} contains a result without case_id.")
        report[case_id] = CaseReport(
            case_id=case_id,
            suite=str(item.get("suite") or ""),
            category=str(item.get("category") or ""),
            passed=bool(item.get("passed")),
            failures=_format_failures(item.get("failures")),
        )
    return report


def load_report_metadata(path: Path) -> dict[str, Any]:
    payload = _load_report_payload(path)
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def build_markdown(
    *,
    before_path: Path,
    after_path: Path,
    before: dict[str, CaseReport],
    after: dict[str, CaseReport],
    before_metadata: dict[str, Any] | None = None,
    after_metadata: dict[str, Any] | None = None,
) -> str:
    summary = compare_summary(before=before, after=after)
    lines = [
        "# Eval comparison",
        "",
        f"- Before: `{before_path.as_posix()}`",
        f"- After: `{after_path.as_posix()}`",
        "",
        "## Report metadata",
        "",
        "| Field | Before | After |",
        "|---|---|---|",
        _metadata_row(
            "Generated at local",
            before_metadata,
            after_metadata,
            "generated_at_local",
        ),
        _metadata_row(
            "Generated at UTC",
            before_metadata,
            after_metadata,
            "generated_at_utc",
        ),
        _metadata_row("Suite", before_metadata, after_metadata, "suite"),
        _metadata_row("Mode", before_metadata, after_metadata, "mode"),
        _metadata_row("Cases path", before_metadata, after_metadata, "cases_path"),
        "",
        "## Summary",
        "",
        "| Metric | Before | After | Delta |",
        "|---|---:|---:|---:|",
        _summary_row("Total", summary.before_total, summary.after_total),
        _summary_row("Passed", summary.before_passed, summary.after_passed),
        _summary_row("Failed", summary.before_failed, summary.after_failed),
        "",
        "## Change summary",
        "",
        "| Change | Count |",
        "|---|---:|",
        f"| ✅ Fixed | {summary.fixed} |",
        f"| 🔴 Regressed | {summary.regressed} |",
        f"| ✅ Still passing | {summary.unchanged_passed} |",
        f"| ❌ Still failing | {summary.unchanged_failed} |",
        f"| ➕ Added cases | {summary.added} |",
        f"| ➖ Removed cases | {summary.removed} |",
        "",
        "## Case comparison",
        "",
        "| Case | Category | Before | After | Change | Before failures |",
        "|---|---|---|---|---|---|",
    ]

    for case_id in sorted(set(before) | set(after)):
        before_case = before.get(case_id)
        after_case = after.get(case_id)
        category = _category(before_case, after_case)
        before_status = _status(before_case)
        after_status = _status(after_case)
        change = _change_label(before_case, after_case)
        before_failures = _failures_text(before_case)
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape(case_id),
                    _escape(category),
                    before_status,
                    after_status,
                    change,
                    _escape(before_failures),
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def compare_summary(
    *,
    before: dict[str, CaseReport],
    after: dict[str, CaseReport],
) -> ComparisonSummary:
    before_passed = sum(1 for item in before.values() if item.passed)
    after_passed = sum(1 for item in after.values() if item.passed)
    all_case_ids = set(before) | set(after)

    fixed = 0
    regressed = 0
    unchanged_passed = 0
    unchanged_failed = 0
    added = 0
    removed = 0

    for case_id in all_case_ids:
        before_case = before.get(case_id)
        after_case = after.get(case_id)
        if before_case is None:
            added += 1
        elif after_case is None:
            removed += 1
        elif not before_case.passed and after_case.passed:
            fixed += 1
        elif before_case.passed and not after_case.passed:
            regressed += 1
        elif before_case.passed and after_case.passed:
            unchanged_passed += 1
        else:
            unchanged_failed += 1

    return ComparisonSummary(
        before_total=len(before),
        before_passed=before_passed,
        before_failed=len(before) - before_passed,
        after_total=len(after),
        after_passed=after_passed,
        after_failed=len(after) - after_passed,
        fixed=fixed,
        regressed=regressed,
        unchanged_passed=unchanged_passed,
        unchanged_failed=unchanged_failed,
        added=added,
        removed=removed,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two eval JSON reports.")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    before = load_report(args.before)
    after = load_report(args.after)
    markdown = build_markdown(
        before_path=args.before,
        after_path=args.after,
        before=before,
        after=after,
        before_metadata=load_report_metadata(args.before),
        after_metadata=load_report_metadata(args.after),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")

    summary = compare_summary(before=before, after=after)
    print(f"Comparison written to {args.output}")
    print(
        "Before: "
        f"{summary.before_passed}/{summary.before_total} passed; "
        "After: "
        f"{summary.after_passed}/{summary.after_total} passed"
    )
    print(f"Fixed: {summary.fixed}; regressed: {summary.regressed}")
    return 0 if summary.regressed == 0 else 1


def _load_report_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _format_failures(raw_failures: object) -> tuple[str, ...]:
    if not isinstance(raw_failures, list):
        return ()
    failures: list[str] = []
    for failure in raw_failures:
        if not isinstance(failure, dict):
            continue
        check = str(failure.get("check") or "check")
        detail = str(failure.get("detail") or "")
        failures.append(f"{check}: {detail}" if detail else check)
    return tuple(failures)


def _metadata_row(
    label: str,
    before_metadata: dict[str, Any] | None,
    after_metadata: dict[str, Any] | None,
    key: str,
) -> str:
    before_value = _metadata_value(before_metadata, key)
    after_value = _metadata_value(after_metadata, key)
    return f"| {label} | `{_escape(before_value)}` | `{_escape(after_value)}` |"


def _metadata_value(metadata: dict[str, Any] | None, key: str) -> str:
    if not metadata:
        return "—"
    value = metadata.get(key)
    if value in (None, ""):
        return "—"
    return str(value)


def _summary_row(label: str, before: int, after: int) -> str:
    delta = after - before
    sign = "+" if delta > 0 else ""
    return f"| {label} | {before} | {after} | {sign}{delta} |"


def _category(
    before_case: CaseReport | None,
    after_case: CaseReport | None,
) -> str:
    case = after_case or before_case
    return case.category if case is not None else ""


def _status(case: CaseReport | None) -> str:
    if case is None:
        return "—"
    return "✅ pass" if case.passed else "❌ fail"


def _change_label(
    before_case: CaseReport | None,
    after_case: CaseReport | None,
) -> str:
    if before_case is None:
        return "➕ added"
    if after_case is None:
        return "➖ removed"
    if not before_case.passed and after_case.passed:
        return "✅ fixed"
    if before_case.passed and not after_case.passed:
        return "🔴 regressed"
    if before_case.passed and after_case.passed:
        return "✅ unchanged"
    return "❌ unchanged"


def _failures_text(case: CaseReport | None) -> str:
    if case is None or not case.failures:
        return ""
    return "<br>".join(case.failures)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    sys.exit(main())
