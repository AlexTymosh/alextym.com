from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from scripts.compare_eval_reports import build_markdown
from scripts.compare_eval_reports import compare_summary
from scripts.compare_eval_reports import load_report
from scripts.run_chat_evals import DEFAULT_CASES_PATH
from scripts.run_chat_evals import load_eval_cases
from scripts.run_chat_evals import make_in_process_requester
from scripts.run_chat_evals import print_report
from scripts.run_chat_evals import results_to_dict
from scripts.run_chat_evals import run_cases


def run_eval_cycle(
    *,
    cases_path: Path,
    suite: str,
    mode: str,
    before_path: Path,
    after_path: Path,
    comparison_path: Path,
) -> int:
    had_previous_after = _has_report(after_path)

    if had_previous_after:
        _rotate_after_to_before(before_path=before_path, after_path=after_path)

    cases = load_eval_cases(cases_path, suite=suite)
    request_chat = make_in_process_requester(mode=mode)
    results = run_cases(cases, request_chat)
    _write_json(after_path, results_to_dict(results))
    print_report(results)

    all_passed = all(result.passed for result in results)
    if not had_previous_after:
        print("")
        print("Baseline eval completed.")
        print(f"Results written to: {after_path}")
        print("No previous after-report existed, so comparison was not created.")
        print("Run the same task again after changes to create a comparison.")
        return 0 if all_passed else 1

    before = load_report(before_path)
    after = load_report(after_path)
    markdown = build_markdown(
        before_path=before_path,
        after_path=after_path,
        before=before,
        after=after,
    )
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.write_text(markdown, encoding="utf-8")

    summary = compare_summary(before=before, after=after)
    print("")
    print("Eval cycle completed.")
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

    return 0 if all_passed and summary.regressed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run evals with automatic before/after rotation.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--mode", choices=("isolated", "live"), required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    args = parser.parse_args(argv)

    return run_eval_cycle(
        cases_path=args.cases,
        suite=args.suite,
        mode=args.mode,
        before_path=args.before,
        after_path=args.after,
        comparison_path=args.comparison,
    )


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


if __name__ == "__main__":
    sys.exit(main())
