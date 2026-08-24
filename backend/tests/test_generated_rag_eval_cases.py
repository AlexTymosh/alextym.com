from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from app.rag.case_study_rag_source import load_case_study_rag_document
from app.rag.query_router import route_query
from app.schemas.chat import ChatRequest
from app.services.chat_intent_resolution import is_weakness_request, resolve_question
from app.services.chat_policy import apply_pre_rag_policy
from scripts.run_chat_evals import load_eval_cases
from scripts.run_retrieval_evals import load_retrieval_eval_cases

LEGACY_CHAT_CASE_IDS = {
    "generated_rag_hard_skills",
    "generated_rag_soft_skills",
    "generated_rag_share_code_handoff",
    "generated_rag_right_to_work",
    "generated_rag_portfolio_project",
    "generated_rag_ai_assisted_workflow",
    "generated_rag_start_date_handoff",
}
CASE_STUDY_COVERAGE_KEYS = {
    "weee_automation",
    "weee_poor_roi",
    "procurement_controls",
    "procurement_bpmn",
    "iot_fault_separation",
    "credit_risk_limitations",
    "payment_reconciliation",
    "skills_verification",
    "international_employment_service",
    "kaizen_service_transformation",
    "recruitment_document_automation",
    "pricing_data_erp_governance",
}
CASE_STUDY_CHAT_CASE_IDS = {f"case_study_{key}" for key in CASE_STUDY_COVERAGE_KEYS}
GENERATED_RAG_CASE_IDS = LEGACY_CHAT_CASE_IDS | CASE_STUDY_CHAT_CASE_IDS
CASE_STUDY_RETRIEVAL_CASE_IDS = {f"retrieval_case_study_{key}" for key in CASE_STUDY_COVERAGE_KEYS}


def test_generated_rag_eval_cases_are_schema_valid() -> None:
    cases = _chat_cases()

    assert {case["id"] for case in cases} == GENERATED_RAG_CASE_IDS
    assert all(case["expected"] for case in cases)
    assert all("site owner" in str(case["message"]).casefold() for case in cases)


def test_case_study_eval_coverage_matches_between_answer_and_retrieval() -> None:
    chat_cases = _case_study_chat_cases()
    retrieval_cases = _case_study_retrieval_cases()

    assert {case["id"] for case in retrieval_cases} == CASE_STUDY_RETRIEVAL_CASE_IDS
    assert {case["coverage_key"] for case in chat_cases} == CASE_STUDY_COVERAGE_KEYS
    assert {case["coverage_key"] for case in retrieval_cases} == CASE_STUDY_COVERAGE_KEYS
    assert all("site owner" in str(case["query"]).casefold() for case in retrieval_cases)

    chat_case_ids = {case["case_id"] for case in chat_cases}
    retrieval_case_ids = {case["case_id"] for case in retrieval_cases}
    canonical_case_ids = set(_chunks_by_case())

    assert chat_case_ids == retrieval_case_ids
    assert chat_case_ids == canonical_case_ids


def test_case_study_questions_preserve_semantics_across_chat_layers() -> None:
    retrieval_by_coverage_key = {
        case["coverage_key"]: case for case in _case_study_retrieval_cases()
    }

    for answer_case in _case_study_chat_cases():
        case_label = str(answer_case["id"])
        message = str(answer_case["message"])
        retrieval_case = retrieval_by_coverage_key[answer_case["coverage_key"]]
        request = ChatRequest(message=message)

        policy_result = apply_pre_rag_policy(
            request,
            is_handoff_request=lambda _message: False,
            is_handoff_confirmation_after_prompt=lambda _request: False,
            is_weakness_request=is_weakness_request,
        )
        assert policy_result is None, case_label

        resolution = resolve_question(request, question_contextualizer=None)
        assert resolution.intent == "alex_profile_question", case_label
        assert resolution.standalone_question == message, case_label

        original_route = route_query(message)
        resolved_route = route_query(resolution.standalone_question)
        assert resolved_route == original_route, case_label
        assert resolved_route.source_scope == "case_studies", case_label
        assert resolved_route.select_single_case is True, case_label
        assert resolved_route.case_section_hints, case_label
        assert retrieval_case["case_id"] == answer_case["case_id"], case_label


def test_case_study_eval_expectations_match_generated_source_metadata() -> None:
    chunks_by_case = _chunks_by_case()

    for case in _case_study_chat_cases():
        case_id = str(case["case_id"])
        chunks = chunks_by_case[case_id]
        expected = case["expected"]

        assert chunks, case_id
        assert set(expected["must_include_source_title_any"]).intersection(
            {chunk.source.title for chunk in chunks}
        )
        assert set(expected["must_include_source_section_any"]).intersection(
            {chunk.source.section for chunk in chunks}
        )

    for case in _case_study_retrieval_cases():
        case_id = str(case["case_id"])
        chunks = chunks_by_case[case_id]
        expected = case["expected"]

        assert chunks, case_id
        assert expected["top_case_id_any"] == [case_id]
        assert set(expected["top_case_section_any"]).intersection(
            {chunk.payload.case_section for chunk in chunks}
        )
        assert set(expected["must_include_case_section_any"]).intersection(
            {chunk.payload.case_section for chunk in chunks}
        )
        assert set(expected["must_include_source_any"]).intersection(
            {chunk.source.title for chunk in chunks}
        )
        assert set(expected["must_include_organization_any"]).intersection(
            {chunk.source.organization for chunk in chunks}
        )


def _chat_cases() -> list[dict[str, object]]:
    eval_file = _backend_root() / "evals" / "chat_eval_cases_generated_rag.json"
    return load_eval_cases(eval_file, suite="rag_generated_quality")


def _retrieval_cases() -> list[dict[str, object]]:
    eval_file = _backend_root() / "evals" / "retrieval_eval_cases_generated_rag.json"
    return load_retrieval_eval_cases(eval_file, suite="rag_retrieval_quality")


def _case_study_chat_cases() -> list[dict[str, object]]:
    return [case for case in _chat_cases() if case["id"] in CASE_STUDY_CHAT_CASE_IDS]


def _case_study_retrieval_cases() -> list[dict[str, object]]:
    return [case for case in _retrieval_cases() if case["id"] in CASE_STUDY_RETRIEVAL_CASE_IDS]


def _chunks_by_case() -> dict[str, list[object]]:
    repository_root = _repository_root()
    document = load_case_study_rag_document(
        case_studies_directory=repository_root / "content" / "public" / "case-studies",
        resume_path=repository_root / "content" / "public" / "resume.md",
        repository_root=repository_root,
    )
    chunks_by_case: dict[str, list[object]] = defaultdict(list)
    for chunk in document.chunks:
        chunks_by_case[chunk.payload.case_id].append(chunk)
    return chunks_by_case


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]
