from app.core.config import Settings
from app.llm.client import EmbeddingClient
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.models import KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore

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
        query_embedding = self._embedding_client.embed_text(normalized_query)
        chunks = self._store.search(
            embedding=query_embedding,
            limit=effective_limit,
            score_threshold=self._score_threshold,
        )
        return _filter_sections_for_query(normalized_query, chunks)


def _filter_sections_for_query(query: str, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    query_terms = set(query.lower().replace("/", " ").replace("-", " ").split())
    if query_terms & LINK_QUERY_TERMS:
        return chunks

    filtered_chunks = [chunk for chunk in chunks if chunk.metadata.topic not in LINK_SECTION_NAMES]
    return filtered_chunks or chunks
