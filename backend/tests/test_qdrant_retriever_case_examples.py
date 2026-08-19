from app.rag.models import ChunkMetadata, KnowledgeChunk, RetrievalFilter
from app.rag.qdrant_retriever import QdrantRetriever
from app.rag.query_router import route_query


END_TO_END_CASE_ID = "case-end-to-end-international-employment-service"
RECRUITMENT_CASE_ID = "case-recruitment-document-automation"


def test_single_example_returns_context_from_one_case_study() -> None:
    employment_overview = _case_chunk(
        chunk_id=f"case:{END_TO_END_CASE_ID}:overview",
        case_id=END_TO_END_CASE_ID,
        source="End-to-End International Employment Service",
        section="overview",
        content="Designed an end-to-end international employment service.",
        retrieval_score=0.95,
    )
    kaizen_context = _case_chunk(
        chunk_id="case:case-kaizen-service-delivery-transformation:context",
        case_id="case-kaizen-service-delivery-transformation",
        source="Kaizen-Driven Service Delivery Transformation",
        section="context",
        content="Improved a service-delivery workflow.",
        retrieval_score=0.45,
    )
    employment_details = [
        _case_chunk(
            chunk_id=f"case:{END_TO_END_CASE_ID}:implementation-coordinated-service",
            case_id=END_TO_END_CASE_ID,
            source="End-to-End International Employment Service",
            section="implementation-coordinated-service",
            content="Coordinated documents, travel, work and housing support.",
            retrieval_score=0.91,
        ),
        _case_chunk(
            chunk_id=f"case:{END_TO_END_CASE_ID}:results",
            case_id=END_TO_END_CASE_ID,
            source="End-to-End International Employment Service",
            section="results",
            content="Standardised the customer journey and reduced repeated questions.",
            retrieval_score=0.82,
        ),
    ]
    store = CaseExampleStore(
        candidates=[employment_overview, kaizen_context],
        selected_case_chunks=employment_details,
    )
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=store,
        default_limit=6,
        score_threshold=0.4,
    )

    result = retriever.retrieve("Give me example of his end-to-end experience")

    assert [chunk.id for chunk in result] == [chunk.id for chunk in employment_details]
    assert {chunk.metadata.source for chunk in result} == {
        "End-to-End International Employment Service"
    }
    assert len(store.calls) == 2
    assert store.calls[0].limit == 36
    assert store.calls[0].payload_filter.source_group_any == ("case-studies",)
    assert store.calls[0].payload_filter.case_id_any == ()
    assert store.calls[1].limit == 18
    assert store.calls[1].payload_filter.source_group_any == ("case-studies",)
    assert store.calls[1].payload_filter.case_id_any == (END_TO_END_CASE_ID,)


def test_single_example_falls_back_to_unified_retrieval_without_case_match() -> None:
    resume_chunk = KnowledgeChunk(
        id="resume:summary",
        content="General professional profile.",
        metadata=ChunkMetadata(
            source="Summary",
            section="summary",
            topic="summary",
            extra={"source_group": "resume", "retrieval_score": 0.8},
        ),
    )
    store = CaseExampleStore(
        candidates=[],
        selected_case_chunks=[],
        fallback_chunks=[resume_chunk],
    )
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=store,
        default_limit=6,
        score_threshold=0.4,
    )

    result = retriever.retrieve("Give me an example of professional experience")

    assert result == [resume_chunk]
    assert len(store.calls) == 2
    assert store.calls[0].payload_filter.source_group_any == ("case-studies",)
    assert store.calls[1].payload_filter.source_group_any == ("resume", "case-studies")


def test_plural_example_requests_keep_case_scope_without_selecting_one_case() -> None:
    examples_route = route_query("Give me examples of his experience")
    case_studies_route = route_query("Show me several case studies")

    assert examples_route.source_scope == "case_studies"
    assert examples_route.select_single_case is False
    assert case_studies_route.source_scope == "case_studies"
    assert case_studies_route.select_single_case is False


def test_selected_case_sections_are_reranked_before_final_limit() -> None:
    overview = _case_chunk(
        chunk_id=f"case:{END_TO_END_CASE_ID}:overview",
        case_id=END_TO_END_CASE_ID,
        source="End-to-End International Employment Service",
        section="overview",
        content="Overview of the employment service.",
        retrieval_score=0.96,
    )
    implementation = _case_chunk(
        chunk_id=f"case:{END_TO_END_CASE_ID}:implementation-coordinated-service",
        case_id=END_TO_END_CASE_ID,
        source="End-to-End International Employment Service",
        section="implementation-coordinated-service",
        content="Implemented a coordinated international employment workflow.",
        retrieval_score=0.72,
    )
    results = _case_chunk(
        chunk_id=f"case:{END_TO_END_CASE_ID}:results",
        case_id=END_TO_END_CASE_ID,
        source="End-to-End International Employment Service",
        section="results",
        content="Reduced repeated questions across the customer journey.",
        retrieval_score=0.68,
    )
    store = CaseExampleStore(
        candidates=[overview],
        selected_case_chunks=[overview, implementation, results],
    )
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=store,
        default_limit=6,
        score_threshold=0.4,
    )

    result = retriever.retrieve(
        "How did the site owner design an end-to-end international employment service?",
        limit=2,
    )

    assert [chunk.id for chunk in result] == [implementation.id, overview.id]
    assert store.calls[0].limit == 36
    assert store.calls[1].limit == 18


def test_case_selection_does_not_reward_cases_with_more_requested_sections() -> None:
    recruitment_candidate = _case_chunk(
        chunk_id=f"case:{RECRUITMENT_CASE_ID}:overview",
        case_id=RECRUITMENT_CASE_ID,
        source="Recruitment Workflow and Document Automation",
        section="overview",
        content="Recruitment workflow and document generation.",
        retrieval_score=0.72,
    )
    kaizen_candidates = [
        _case_chunk(
            chunk_id=f"case:case-kaizen-service-delivery-transformation:implementation-{index}",
            case_id="case-kaizen-service-delivery-transformation",
            source="Kaizen-Driven Service Delivery Transformation",
            section=f"implementation-{index}",
            content="Implemented a generic service workflow.",
            retrieval_score=score,
        )
        for index, score in enumerate((0.90, 0.88, 0.86), start=1)
    ]
    recruitment_implementation = _case_chunk(
        chunk_id=f"case:{RECRUITMENT_CASE_ID}:implementation-customer-data-and-documents",
        case_id=RECRUITMENT_CASE_ID,
        source="Recruitment Workflow and Document Automation",
        section="implementation-customer-data-and-documents",
        content="Automated recruitment documents from structured customer data.",
        retrieval_score=0.70,
    )
    store = CaseExampleStore(
        candidates=[*kaizen_candidates, recruitment_candidate],
        selected_case_chunks=[recruitment_implementation],
    )
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=store,
        default_limit=6,
        score_threshold=0.4,
    )

    result = retriever.retrieve(
        "How did the site owner automate recruitment workflows and document generation?"
    )

    assert result == [recruitment_implementation]
    assert store.calls[1].payload_filter.case_id_any == (RECRUITMENT_CASE_ID,)


def _case_chunk(
    *,
    chunk_id: str,
    case_id: str,
    source: str,
    section: str,
    content: str,
    retrieval_score: float,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            source=source,
            section="experience",
            topic=f"{case_id.removeprefix('case-')}-{section}",
            tags=("case-study", "experience"),
            extra={
                "source_group": "case-studies",
                "document_type": "case-study",
                "case_id": case_id,
                "case_section": section,
                "parent_id": f"case:{case_id}",
                "retrieval_score": retrieval_score,
            },
        ),
    )


class FakeEmbeddingClient:
    def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2]


class SearchCall:
    def __init__(
        self,
        *,
        limit: int,
        payload_filter: RetrievalFilter,
    ) -> None:
        self.limit = limit
        self.payload_filter = payload_filter


class CaseExampleStore:
    def __init__(
        self,
        *,
        candidates: list[KnowledgeChunk],
        selected_case_chunks: list[KnowledgeChunk],
        fallback_chunks: list[KnowledgeChunk] | None = None,
    ) -> None:
        self._candidates = candidates
        self._selected_case_chunks = selected_case_chunks
        self._fallback_chunks = fallback_chunks or []
        self.calls: list[SearchCall] = []

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
        payload_filter: RetrievalFilter | None = None,
    ) -> list[KnowledgeChunk]:
        assert payload_filter is not None
        self.calls.append(SearchCall(limit=limit, payload_filter=payload_filter))

        if payload_filter.source_group_any == ("case-studies",):
            if payload_filter.case_id_any:
                return self._selected_case_chunks
            return self._candidates
        return self._fallback_chunks
