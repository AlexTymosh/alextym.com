from __future__ import annotations

from pathlib import Path

from scripts.run_chat_evals import load_eval_cases

GENERATED_RAG_CASE_IDS = {
    "generated_rag_hard_skills",
    "generated_rag_soft_skills",
    "generated_rag_share_code_handoff",
    "generated_rag_right_to_work",
    "generated_rag_portfolio_project",
    "generated_rag_ai_assisted_workflow",
    "generated_rag_start_date_handoff",
}


def test_generated_rag_eval_cases_are_schema_valid() -> None:
    eval_file = Path(__file__).resolve().parents[1] / "evals" / "chat_eval_cases_generated_rag.json"

    cases = load_eval_cases(eval_file, suite="rag_generated_quality")

    assert {case["id"] for case in cases} == GENERATED_RAG_CASE_IDS
    assert all(case["expected"] for case in cases)
