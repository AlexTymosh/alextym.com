from app.core.config import Settings
from app.llm.client import EmbeddingClient
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.models import KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore


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
        return self._store.search(
            embedding=query_embedding,
            limit=effective_limit,
            score_threshold=self._score_threshold,
        )
