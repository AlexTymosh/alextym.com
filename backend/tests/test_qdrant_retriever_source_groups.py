from app.rag.models import RetrievalFilter
from app.rag.qdrant_retriever import (
    QdrantRetriever,
    _with_current_public_source_groups,
)


def test_retriever_searches_current_resume_and_case_study_groups() -> None:
    store = CapturingStore()
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=store,
        default_limit=6,
        score_threshold=0.4,
    )

    assert retriever.retrieve("How did the site owner automate WEEE reporting?") == []

    assert store.payload_filter is not None
    assert store.payload_filter.source_group_any == ("resume", "case-studies")


def test_current_source_group_filter_preserves_route_selectors() -> None:
    original = RetrievalFilter(
        topic_any=("hard-skills",),
        tag_any=("python", "automation"),
        section_any=("experience",),
    )

    updated = _with_current_public_source_groups(original)

    assert updated.source_group_any == ("resume", "case-studies")
    assert updated.topic_any == original.topic_any
    assert updated.tag_any == original.tag_any
    assert updated.section_any == original.section_any


class FakeEmbeddingClient:
    def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2]


class CapturingStore:
    def __init__(self) -> None:
        self.payload_filter: RetrievalFilter | None = None

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
        payload_filter: RetrievalFilter | None = None,
    ) -> list[object]:
        self.payload_filter = payload_filter
        return []
