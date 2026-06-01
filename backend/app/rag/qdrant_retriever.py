import inspect

from app.core.config import Settings
from app.llm.client import EmbeddingClient
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.models import KnowledgeChunk, RetrievalFilter
from app.rag.qdrant_store import QdrantKnowledgeStore
from app.rag.query_router import route_query

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
            "баз",
            "данн",
            "субд",
        ),
        "SQL PostgreSQL SQLAlchemy Alembic relational databases database-backed workflows",
    ),
    (
        ("fastapi", "backend", "api", "бекенд", "бэкенд", "апи"),
        "Python FastAPI backend REST APIs request response validation internal services",
    ),
    (
        ("rag", "llm", "ai-assisted", "assistant", "ассист", "ии", "нейро"),
        "RAG AI-assisted development knowledge-base assistants LLM automation workflows",
    ),
    (
        ("project", "projects", "portfolio", "repo", "repository", "проект"),
        "projects repositories portfolio FastAPI RAG automation backend templates",
    ),
    (
        (
            "experience",
            "skills",
            "worked",
            "used",
            "опыт",
            "работал",
            "умеет",
            "навык",
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
        return _filter_sections_for_query(normalized_query, chunks)


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
