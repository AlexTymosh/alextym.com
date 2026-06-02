from app.rag.keyword_scoring import build_keyword_terms, keyword_score_chunk
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.query_router import route_query


def test_build_keyword_terms_includes_query_and_route_hints() -> None:
    route = route_query("Tell me about Alex's RAG portfolio project.")

    terms = build_keyword_terms(
        "Tell me about Alex's RAG portfolio project.",
        route=route,
    )

    assert "rag" in terms
    assert "portfolio" in terms
    assert "project-ai-portfolio-rag-chat" in terms
    assert "project" in terms


def test_build_keyword_terms_splits_hyphenated_terms() -> None:
    route = route_query("Can Alex provide a share code?")

    terms = build_keyword_terms("share-code", route=route)

    assert "share-code" in terms
    assert "share" in terms
    assert "code" in terms


def test_keyword_score_chunk_uses_tags_answer_facts_and_sparse_keywords() -> None:
    route = route_query("Does Alex use Bitrix24 integrations?")
    terms = build_keyword_terms("Does Alex use Bitrix24 integrations?", route=route)
    chunk = KnowledgeChunk(
        id="bitrix",
        content="Internal tooling work.",
        metadata=ChunkMetadata(
            source="Business Systems",
            section="experience",
            topic="business-systems",
            tags=("crm",),
            extra={
                "answer_facts": ["Alex has worked with Bitrix24-style CRM flows."],
                "vector_inputs": {"keywords_sparse": "bitrix24 crm integration"},
            },
        ),
    )

    assert keyword_score_chunk(chunk, query_terms=terms) > 0.0


def test_keyword_score_chunk_returns_zero_without_meaningful_overlap() -> None:
    route = route_query("Does Alex use Bitrix24 integrations?")
    terms = build_keyword_terms("Does Alex use Bitrix24 integrations?", route=route)
    chunk = KnowledgeChunk(
        id="summary",
        content="Alex works with Python APIs.",
        metadata=ChunkMetadata(
            source="Summary",
            section="summary",
            topic="summary",
            tags=("python",),
        ),
    )

    assert keyword_score_chunk(chunk, query_terms=terms) == 0.0


def test_keyword_terms_ignore_generic_profile_hints_for_unknown_queries() -> None:
    route = route_query("Does Alex use Bitrix24 integrations?")

    terms = build_keyword_terms("Does Alex use Bitrix24 integrations?", route=route)

    assert route.intent == "general_profile"
    assert "summary" not in terms
    assert "profile" not in terms
    assert "experience" not in terms
    assert "bitrix24" in terms
    assert "integration" in terms
