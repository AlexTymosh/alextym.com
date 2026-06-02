from types import SimpleNamespace

from app.rag.models import RetrievalFilter
from app.rag.qdrant_store import QdrantKnowledgeStore


def test_qdrant_store_search_builds_payload_filter() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=fake_qdrant,
    )

    store.search(
        embedding=[0.1, 0.2],
        limit=5,
        score_threshold=0.7,
        payload_filter=RetrievalFilter(
            topic_any=("right-to-work-uk-location",),
            tag_any=("share-code", "right-to-work"),
            section_any=("experience",),
        ),
    )

    query_filter = fake_qdrant.last_query_kwargs["query_filter"]

    assert query_filter is not None
    assert [condition.key for condition in query_filter.must] == ["visibility"]
    assert [condition.key for condition in query_filter.should] == [
        "topic",
        "tags",
        "section",
    ]
    assert query_filter.should[0].match.any == ["right-to-work-uk-location"]
    assert query_filter.should[1].match.any == ["share-code", "right-to-work"]
    assert query_filter.should[2].match.any == ["experience"]


def test_qdrant_store_search_omits_filter_when_not_requested() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=fake_qdrant,
    )

    store.search(embedding=[0.1, 0.2], limit=5, score_threshold=0.7)

    assert fake_qdrant.last_query_kwargs["query_filter"] is None


class FakeQdrantClient:
    def __init__(self) -> None:
        self.last_query_kwargs: dict[str, object] = {}

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.last_query_kwargs = kwargs
        return SimpleNamespace(points=[])
