import inspect

from app.core.config import Settings
from app.llm.client import EmbeddingClient
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.keyword_scoring import build_keyword_terms, keyword_score_chunk
from app.rag.models import KnowledgeChunk, RetrievalFilter
from app.rag.qdrant_store import QdrantKnowledgeStore
from app.rag.query_router import QueryRoute, route_query

QUERY_EXPANSIONS = (
    (
        (
            "sql",
            "postgres",
            "postgresql",
            "sqlalchemy",
            "alembic",
            "database",
            "databases",
            "\u0431\u0430\u0437",
            "\u0434\u0430\u043d\u043d",
            "\u0441\u0443\u0431\u0434",
        ),
        ("SQL PostgreSQL SQLAlchemy Alembic relational databases database-backed workflows"),
    ),
    (
        (
            "fastapi",
            "backend",
            "api",
            "\u0431\u0435\u043a\u0435\u043d\u0434",
            "\u0431\u044d\u043a\u0435\u043d\u0434",
            "\u0430\u043f\u0438",
        ),
        ("Python FastAPI backend REST APIs request response validation internal services"),
    ),
    (
        (
            "rag",
            "llm",
            "ai-assisted",
            "assistant",
            "\u0430\u0441\u0441\u0438\u0441\u0442",
            "\u0438\u0438",
            "\u043d\u0435\u0439\u0440\u043e",
        ),
        ("RAG AI-assisted development knowledge-base assistants LLM automation workflows"),
    ),
    (
        (
            "service",
            "services",
            "website",
            "web app",
            "internal tool",
            "business automation",
            "collaboration",
            "build software",
            "build an app",
        ),
        (
            "software services websites internal tools API integrations business "
            "automation RAG chatbot collaboration project enquiry"
        ),
    ),
    (
        (
            "strength",
            "strengths",
            "different",
            "advantage",
            "why hire",
            "what makes",
            "stands out",
        ),
        (
            "professional strengths automation-first thinking analytical "
            "business process understanding collaboration working style"
        ),
    ),
    (
        ("weakness", "weaknesses", "development area", "areas to improve"),
        "public boundary development areas direct professional conversation",
    ),
    (
        (
            "project",
            "projects",
            "portfolio",
            "repo",
            "repository",
            "\u043f\u0440\u043e\u0435\u043a\u0442",
        ),
        "projects repositories portfolio FastAPI RAG automation backend templates",
    ),
    (
        (
            "experience",
            "skills",
            "worked",
            "used",
            "\u043e\u043f\u044b\u0442",
            "\u0440\u0430\u0431\u043e\u0442\u0430\u043b",
            "\u0443\u043c\u0435\u0435\u0442",
            "\u043d\u0430\u0432\u044b\u043a",
        ),
        "experience skills practical work used implemented built",
    ),
)

LINK_SECTION_NAMES = {"links", "references"}
LINK_QUERY_TERMS = {
    "contact",
    "github",
    "linkedin",
    "link",
    "links",
    "repo",
    "repository",
    "website",
}


class QdrantRetriever:
    def __init__(
        self,
        *,
        embedding_client: EmbeddingClient,
        store: QdrantKnowledgeStore,
        default_limit: int,
        score_threshold: float,
    ) -> None:
        self._embedding_client = embedding_client
        self._store = store
        self._default_limit = default_limit
        self._score_threshold = score_threshold

    @classmethod
    def from_settings(cls, settings: Settings) -> "QdrantRetriever":
        return cls(
            embedding_client=OpenAIEmbeddingClient.from_settings(settings),
            store=QdrantKnowledgeStore.from_settings(settings),
            default_limit=settings.rag_top_k,
            score_threshold=settings.rag_score_threshold,
        )

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        effective_limit = limit or self._default_limit
        route = route_query(normalized_query)
        routed_query = route.retrieval_text(normalized_query)
        payload_filter = route.payload_filter()
        query_embedding = self._embedding_client.embed_text(_expand_query(routed_query))
        chunks = _search_store(
            store=self._store,
            embedding=query_embedding,
            limit=effective_limit,
            score_threshold=self._score_threshold,
            payload_filter=payload_filter,
        )
        filtered_chunks = _filter_sections_for_query(normalized_query, chunks)
        return _rerank_chunks(filtered_chunks, query=normalized_query, route=route)


def _search_store(
    *,
    store: QdrantKnowledgeStore,
    embedding: list[float],
    limit: int,
    score_threshold: float,
    payload_filter: RetrievalFilter | None,
) -> list[KnowledgeChunk]:
    if _store_accepts_payload_filter(store):
        return store.search(
            embedding=embedding,
            limit=limit,
            score_threshold=score_threshold,
            payload_filter=payload_filter,
        )

    return store.search(
        embedding=embedding,
        limit=limit,
        score_threshold=score_threshold,
    )


def _store_accepts_payload_filter(store: object) -> bool:
    try:
        signature = inspect.signature(store.search)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        return True

    return "payload_filter" in signature.parameters


def _expand_query(query: str) -> str:
    normalized_query = query.casefold()
    expansions = [
        expansion
        for triggers, expansion in QUERY_EXPANSIONS
        if any(trigger in normalized_query for trigger in triggers)
    ]
    if not expansions:
        return query
    return " ".join([query, *expansions])


def _filter_sections_for_query(
    query: str,
    chunks: list[KnowledgeChunk],
) -> list[KnowledgeChunk]:
    query_terms = set(query.lower().replace("/", " ").replace("-", " ").split())
    if query_terms & LINK_QUERY_TERMS:
        return chunks

    filtered_chunks = [chunk for chunk in chunks if chunk.metadata.topic not in LINK_SECTION_NAMES]
    return filtered_chunks or chunks


def _rerank_chunks(
    chunks: list[KnowledgeChunk],
    *,
    query: str,
    route: QueryRoute,
) -> list[KnowledgeChunk]:
    if not chunks:
        return []

    keyword_terms = build_keyword_terms(query, route=route)
    scored_chunks = [
        (
            _heuristic_score(
                chunk,
                route=route,
                keyword_terms=keyword_terms,
            ),
            index,
            chunk,
        )
        for index, chunk in enumerate(chunks)
    ]
    scored_chunks.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _score, _index, chunk in scored_chunks]


def _heuristic_score(
    chunk: KnowledgeChunk,
    *,
    route: QueryRoute,
    keyword_terms: frozenset[str],
) -> float:
    score = _dense_score(chunk)
    score += _topic_bonus(chunk, route)
    score += _tag_bonus(chunk, route)
    score += _section_bonus(chunk, route)
    score += keyword_score_chunk(chunk, query_terms=keyword_terms)
    return score


def _dense_score(chunk: KnowledgeChunk) -> float:
    value = chunk.metadata.extra.get("retrieval_score")
    return float(value) if isinstance(value, (int, float)) else 0.0


def _topic_bonus(chunk: KnowledgeChunk, route: QueryRoute) -> float:
    if chunk.metadata.topic in route.topic_hints:
        return 2.0
    return 0.0


def _tag_bonus(chunk: KnowledgeChunk, route: QueryRoute) -> float:
    if not route.tag_hints:
        return 0.0

    matching_tags = set(chunk.metadata.tags).intersection(route.tag_hints)
    return 0.4 * len(matching_tags)


def _section_bonus(chunk: KnowledgeChunk, route: QueryRoute) -> float:
    normalized_section = chunk.metadata.section.casefold()
    normalized_hints = {hint.casefold() for hint in route.section_hints}
    if normalized_section in normalized_hints:
        return 0.25
    return 0.0
