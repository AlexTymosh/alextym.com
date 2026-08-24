from app.rag.models import RetrievalFilter
from app.rag.qdrant_retriever import QdrantRetriever


def test_retriever_searches_current_resume_and_case_study_groups() -> None:
    store = CapturingStore()
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=store,
        default_limit=6,
        score_threshold=0.4,
    )

    assert retriever.retrieve("How did the site owner automate WEEE reporting?") == []

    assert [call.source_group_any for call in store.payload_filters] == [
        ("case-studies",),
        ("resume", "case-studies"),
    ]


def test_commercial_service_route_searches_resume_only() -> None:
    store = CapturingStore()
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=store,
        default_limit=6,
        score_threshold=0.4,
    )

    assert retriever.retrieve("What services does Alex offer?") == []

    assert [call.source_group_any for call in store.payload_filters] == [("resume",)]


class FakeEmbeddingClient:
    def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2]


class CapturingStore:
    def __init__(self) -> None:
        self.payload_filters: list[RetrievalFilter] = []

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
        payload_filter: RetrievalFilter | None = None,
    ) -> list[object]:
        assert payload_filter is not None
        self.payload_filters.append(payload_filter)
        return []
