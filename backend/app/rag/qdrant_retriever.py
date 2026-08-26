from dataclasses import replace
from typing import Protocol

from app.core.config import Settings
from app.llm.client import EmbeddingClient, ProviderConfigurationError, ProviderRequestError
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.collection_contract import CASE_STUDY_SOURCE_GROUP, PUBLIC_SOURCE_GROUPS
from app.rag.errors import RetrievalError
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
_GENERAL_MIN_CANDIDATES = 18
_GENERAL_CANDIDATE_MULTIPLIER = 3
_CASE_SELECTION_MIN_CANDIDATES = 36
_CASE_SELECTION_CANDIDATE_MULTIPLIER = 6
_CASE_SECTION_MIN_CANDIDATES = 18
_CASE_SECTION_CANDIDATE_MULTIPLIER = 3
_CASE_SECTION_BONUS = 2.25


class QdrantRetriever:
    def __init__(
        self,
        *,
        embedding_client: EmbeddingClient,
        store: "KnowledgeSearchStore",
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
        query_embedding = _embed_query(
            self._embedding_client,
            _expand_query(routed_query),
        )

        if route.select_single_case:
            case_chunks = self._retrieve_selected_case(
                query=normalized_query,
                route=route,
                query_embedding=query_embedding,
                limit=effective_limit,
            )
            if case_chunks:
                return case_chunks

            route = replace(
                route,
                source_scope="all",
                select_single_case=False,
            )

        return self._retrieve_ranked_candidates(
            query=normalized_query,
            route=route,
            query_embedding=query_embedding,
            limit=effective_limit,
        )

    def _retrieve_ranked_candidates(
        self,
        *,
        query: str,
        route: QueryRoute,
        query_embedding: list[float],
        limit: int,
    ) -> list[KnowledgeChunk]:
        candidate_limit = max(
            _GENERAL_MIN_CANDIDATES,
            limit * _GENERAL_CANDIDATE_MULTIPLIER,
        )
        chunks = _search_store(
            store=self._store,
            embedding=query_embedding,
            limit=candidate_limit,
            score_threshold=self._score_threshold,
            payload_filter=_route_payload_filter(route),
        )
        filtered_chunks = _filter_sections_for_query(query, chunks)
        return _rerank_chunks(filtered_chunks, query=query, route=route)[:limit]

    def _retrieve_selected_case(
        self,
        *,
        query: str,
        route: QueryRoute,
        query_embedding: list[float],
        limit: int,
    ) -> list[KnowledgeChunk]:
        candidate_limit = max(
            _CASE_SELECTION_MIN_CANDIDATES,
            limit * _CASE_SELECTION_CANDIDATE_MULTIPLIER,
        )
        candidate_chunks = _search_store(
            store=self._store,
            embedding=query_embedding,
            limit=candidate_limit,
            score_threshold=self._score_threshold,
            payload_filter=_case_study_filter(),
        )
        filtered_candidates = _filter_sections_for_query(query, candidate_chunks)
        selected_case_id = _select_case_id(
            filtered_candidates,
            query=query,
            route=route,
        )
        if selected_case_id is None:
            return []

        section_candidate_limit = max(
            _CASE_SECTION_MIN_CANDIDATES,
            limit * _CASE_SECTION_CANDIDATE_MULTIPLIER,
        )
        case_chunks = _search_store(
            store=self._store,
            embedding=query_embedding,
            limit=section_candidate_limit,
            score_threshold=self._score_threshold,
            payload_filter=_case_study_filter(case_id=selected_case_id),
        )
        ranked_sections = _rerank_chunks(
            _filter_sections_for_query(query, case_chunks),
            query=query,
            route=route,
        )
        return ranked_sections[:limit]


class KnowledgeSearchStore(Protocol):
    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
        payload_filter: RetrievalFilter | None = None,
    ) -> list[KnowledgeChunk]: ...


def _search_store(
    *,
    store: KnowledgeSearchStore,
    embedding: list[float],
    limit: int,
    score_threshold: float,
    payload_filter: RetrievalFilter | None,
) -> list[KnowledgeChunk]:
    return store.search(
        embedding=embedding,
        limit=limit,
        score_threshold=score_threshold,
        payload_filter=payload_filter,
    )


def _embed_query(
    embedding_client: EmbeddingClient,
    query: str,
) -> list[float]:
    try:
        return embedding_client.embed_text(query)
    except ProviderConfigurationError as exc:
        raise RetrievalError(
            "Embedding provider is not configured for retrieval.",
            stage="embedding",
            code="embedding_not_configured",
            retryable=False,
        ) from exc
    except ProviderRequestError as exc:
        raise RetrievalError(
            "Embedding request failed during retrieval.",
            stage="embedding",
            code="embedding_request_failed",
            retryable=True,
        ) from exc


def _route_payload_filter(route: QueryRoute) -> RetrievalFilter:
    return route.payload_filter() or RetrievalFilter(
        source_group_any=PUBLIC_SOURCE_GROUPS,
    )


def _case_study_filter(*, case_id: str | None = None) -> RetrievalFilter:
    return RetrievalFilter(
        source_group_any=(CASE_STUDY_SOURCE_GROUP,),
        case_id_any=(case_id,) if case_id else (),
    )


def _select_case_id(
    chunks: list[KnowledgeChunk],
    *,
    query: str,
    route: QueryRoute,
) -> str | None:
    case_selection_route = replace(route, case_section_hints=())
    grouped_scores: dict[str, list[tuple[float, int]]] = {}
    for score, index, chunk in _score_chunks(
        chunks,
        query=query,
        route=case_selection_route,
    ):
        case_id = _case_id(chunk)
        if case_id is None:
            continue
        grouped_scores.setdefault(case_id, []).append((score, index))

    if not grouped_scores:
        return None

    return max(
        grouped_scores,
        key=lambda case_id: _case_group_score(grouped_scores[case_id]),
    )


def _case_group_score(scores: list[tuple[float, int]]) -> tuple[float, int]:
    ranked = sorted(scores, key=lambda item: (-item[0], item[1]))
    best_score, best_index = ranked[0]
    supporting_score = sum(score for score, _index in ranked[1:3]) * 0.15
    evidence_bonus = min(3, len(ranked)) * 0.05
    return best_score + supporting_score + evidence_bonus, -best_index


def _case_id(chunk: KnowledgeChunk) -> str | None:
    case_id = chunk.metadata.extra.get("case_id")
    if not isinstance(case_id, str):
        return None
    normalized_case_id = case_id.strip()
    return normalized_case_id or None


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

    scored_chunks = _score_chunks(chunks, query=query, route=route)
    scored_chunks.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _score, _index, chunk in scored_chunks]


def _score_chunks(
    chunks: list[KnowledgeChunk],
    *,
    query: str,
    route: QueryRoute,
) -> list[tuple[float, int, KnowledgeChunk]]:
    keyword_terms = build_keyword_terms(query, route=route)
    return [
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
    score += _case_section_bonus(chunk, route)
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


def _case_section_bonus(chunk: KnowledgeChunk, route: QueryRoute) -> float:
    if not route.case_section_hints:
        return 0.0

    section_intent = _case_section_intent(chunk)
    if section_intent not in route.case_section_hints:
        return 0.0

    priority = route.case_section_hints.index(section_intent)
    return max(1.25, _CASE_SECTION_BONUS - (0.25 * priority))


def _case_section_intent(chunk: KnowledgeChunk) -> str | None:
    value = chunk.metadata.extra.get("case_section")
    if not isinstance(value, str):
        return None

    section = value.strip().casefold()
    if section.startswith("implementation"):
        return "implementation"
    if section.startswith("validation") or section == "decision":
        return "validation"
    if section in {"limitations", "constraints"}:
        return "limitations"
    if section == "results":
        return "results"
    if section == "problem":
        return "problem"
    if section == "analysis" or section.startswith(("first-fault", "second-fault")):
        return "analysis"
    return None
