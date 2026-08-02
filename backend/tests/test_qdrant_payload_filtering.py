from types import SimpleNamespace

from app.rag.models import RetrievalFilter
from app.rag.qdrant_store import QdrantKnowledgeStore


def test_qdrant_store_search_builds_payload_filter() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="public_knowledge",
        client=fake_qdrant,
    )

    store.search(
        embedding=[0.1, 0.2],
        limit=5,
        score_threshold=0.7,
        payload_filter=RetrievalFilter(
            topic_any=("procurement-order-control-analysis",),
            tag_any=("bpmn", "procurement"),
            section_any=("experience",),
            document_type_any=("case-study",),
            source_group_any=("case-studies",),
            case_id_any=("case-procurement-order-control",),
            case_section_any=("analysis",),
        ),
    )

    query_filter = fake_qdrant.last_query_kwargs["query_filter"]

    assert query_filter is not None
    assert [condition.key for condition in query_filter.must] == [
        "visibility",
        "document_type",
        "source_group",
        "case_id",
        "case_section",
    ]
    assert [condition.key for condition in query_filter.should] == [
        "topic",
        "tags",
        "section",
    ]
    assert query_filter.must[1].match.any == ["case-study"]
    assert query_filter.must[2].match.any == ["case-studies"]
    assert query_filter.must[3].match.any == ["case-procurement-order-control"]
    assert query_filter.must[4].match.any == ["analysis"]
    assert query_filter.should[0].match.any == ["procurement-order-control-analysis"]
    assert query_filter.should[1].match.any == ["bpmn", "procurement"]
    assert query_filter.should[2].match.any == ["experience"]


def test_qdrant_store_search_omits_filter_when_not_requested() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="public_knowledge",
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
