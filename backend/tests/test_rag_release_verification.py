from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import get_settings
from app.rag.models import ChunkMetadata, KnowledgeChunk
from scripts.verify_rag_release import DEFAULT_CANARIES_PATH
from scripts.verify_rag_release import ReleaseCanary
from scripts.verify_rag_release import ReleaseVerificationError
from scripts.verify_rag_release import load_release_canaries
from scripts.verify_rag_release import parse_sse_chat_response
from scripts.verify_rag_release import verify_collection_contract
from scripts.verify_rag_release import verify_deployed_api
from scripts.verify_rag_release import verify_retrieval_canaries
from scripts.verify_rag_release import verify_retrieval_error_metrics


def test_bundled_release_canaries_resolve_canonical_eval_cases() -> None:
    canaries = load_release_canaries(DEFAULT_CANARIES_PATH)

    assert [canary.id for canary in canaries] == [
        "credit-risk-limitations",
        "international-employment-service",
    ]
    assert all(
        canary.retrieval_case["query"] == canary.answer_case["message"] for canary in canaries
    )
    assert all(canary.expected_case_id.startswith("case-") for canary in canaries)
    assert all(canary.expected_case_sections for canary in canaries)


def test_collection_probe_uses_runtime_contract_without_mutation() -> None:
    settings = replace(
        get_settings(),
        qdrant_url="https://qdrant.example.test",
        qdrant_collection="release-alias",
        qdrant_vector_mode="single",
        openai_embedding_dimensions=1536,
    )
    store = RecordingStore()

    report = verify_collection_contract(settings=settings, store=store)

    assert report["status"] == "passed"
    assert report["collection"] == "release-alias"
    assert store.contract.vector_mode == "single"
    assert store.contract.required_source_groups == ("resume", "case-studies")


def test_retrieval_canary_requires_expected_case_and_section() -> None:
    canary = _canary()

    report = verify_retrieval_canaries(
        [canary],
        retriever=StaticRetriever([_chunk(case_id="case-target", case_section="limitations")]),
    )

    assert report["status"] == "passed"

    with pytest.raises(ReleaseVerificationError, match="must_include_case_id_any"):
        verify_retrieval_canaries(
            [canary],
            retriever=StaticRetriever(
                [_chunk(case_id="case-unrelated", case_section="limitations")]
            ),
        )


def test_deployed_api_requires_json_sse_parity_and_case_attribution() -> None:
    canary = _canary()
    response = _api_response()

    report = verify_deployed_api(
        [canary],
        client=StaticApiClient(json_response=response, stream_response=response),
    )

    assert report["status"] == "passed"

    mismatched_stream = {
        **response,
        "sources": [{**response["sources"][0], "case_section": "implementation"}],
    }
    with pytest.raises(ReleaseVerificationError, match="failed sse checks"):
        verify_deployed_api(
            [canary],
            client=StaticApiClient(
                json_response=response,
                stream_response=mismatched_stream,
            ),
        )


def test_sse_parser_reconstructs_answer_sources_and_done_contract() -> None:
    body = "\n".join(
        [
            "event: token",
            'data: {"text":"Grounded "}',
            "",
            "event: token",
            'data: {"text":"answer."}',
            "",
            "event: sources",
            (
                'data: {"sources":[{"title":"Target case","section":"experience",'
                '"confidence":"medium","case_id":"case-target",'
                '"case_section":"limitations"}]}'
            ),
            "",
            "event: done",
            (
                'data: {"confidence":"medium","not_enough_data":false,'
                '"retrieval_status":"success","handoff_suggested":false,'
                '"handoff_reason":null,"language_unsupported":false,'
                '"user_requested_human":false}'
            ),
            "",
        ]
    )

    response = parse_sse_chat_response(body)

    assert response["answer"] == "Grounded answer."
    assert response["sources"][0]["case_id"] == "case-target"
    assert response["retrieval_status"] == "success"


def test_metrics_gate_rejects_qdrant_retrieval_errors() -> None:
    clean_metrics = (
        'portfolio_rag_retrievals_total{error_code="none",outcome="success",stage="complete"} 4\n'
    )
    failed_metrics = (
        'portfolio_rag_retrievals_total{error_code="vector_search_failed",'
        'outcome="error",stage="vector_search"} 1\n'
    )

    assert verify_retrieval_error_metrics(clean_metrics)["qdrant_error_count"] == 0
    with pytest.raises(ReleaseVerificationError, match="exceed"):
        verify_retrieval_error_metrics(failed_metrics)

    with pytest.raises(ReleaseVerificationError, match="missing"):
        verify_retrieval_error_metrics("portfolio_chat_requests_total 4\n")


def _canary() -> ReleaseCanary:
    message = "What limitations applied to the target case?"
    return ReleaseCanary(
        id="target-limitations",
        retrieval_case={
            "id": "retrieval-target",
            "suite": "rag_retrieval_quality",
            "category": "limitations",
            "query": message,
            "limit": 6,
            "expected": {
                "min_results": 1,
                "top_case_id_any": ["case-target"],
                "top_case_section_any": ["limitations"],
                "must_include_case_id_any": ["case-target"],
                "must_include_case_section_any": ["limitations"],
            },
        },
        answer_case={
            "id": "answer-target",
            "suite": "rag_generated_quality",
            "category": "limitations",
            "message": message,
            "expected": {
                "not_enough_data": False,
                "sources": "non_empty",
                "must_include_source_title_any": ["Target case"],
                "must_include_source_section_any": ["experience"],
            },
        },
        expected_case_id="case-target",
        expected_case_sections=("limitations",),
    )


def _chunk(*, case_id: str, case_section: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=f"case:{case_id}:{case_section}",
        content="Public case-study evidence.",
        metadata=ChunkMetadata(
            source="Target case",
            section="experience",
            topic="target-case-limitations",
            extra={
                "case_id": case_id,
                "case_section": case_section,
                "document_type": "case-study",
                "source_group": "case-studies",
            },
        ),
    )


def _api_response() -> dict[str, object]:
    return {
        "answer": "Grounded answer.",
        "sources": [
            {
                "title": "Target case",
                "section": "experience",
                "confidence": "medium",
                "case_id": "case-target",
                "case_section": "limitations",
            }
        ],
        "confidence": "medium",
        "not_enough_data": False,
        "retrieval_status": "success",
        "handoff_suggested": False,
        "handoff_reason": None,
        "language_unsupported": False,
        "user_requested_human": False,
    }


class RecordingStore:
    contract = None

    def validate_contract(self, contract) -> None:
        self.contract = contract


class StaticRetriever:
    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self._chunks = chunks

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        return self._chunks[:limit]


class StaticApiClient:
    def __init__(
        self,
        *,
        json_response: dict[str, object],
        stream_response: dict[str, object],
    ) -> None:
        self._json_response = json_response
        self._stream_response = stream_response

    def readiness(self) -> dict[str, object]:
        return {
            "status": "ready",
            "vector_db": "ready",
            "llm_config": "configured",
        }

    def chat_json(self, payload: dict[str, object]) -> dict[str, object]:
        return self._json_response

    def chat_stream(self, payload: dict[str, object]) -> dict[str, object]:
        return self._stream_response
